import os
import uuid
from pathlib import Path
from typing import Any
import asyncio
from jose import jwt, JWTError
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Header

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALG = "HS256"
ACCESS_TOKEN_MINUTES = 60

ALLOWED_EMAILS = set(
    x.strip().lower()
    for x in os.getenv("ALLOWED_EMAILS", "").split(",")
    if x.strip()
)


UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def create_access_token(email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_TOKEN_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def verify_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        email = payload.get("sub")
        if not email:
            raise ValueError("missing sub")
        return str(email)
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock this down later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def route_agent(user_text: str) -> str:
    """
    Tiny agent router.
    Replace with something smarter when you add more agents.
    """
    t = user_text.lower()
    if "summarize" in t or "summary" in t:
        return "summarizer"
    if "extract" in t or "entities" in t:
        return "extractor"
    return "general"

async def call_model_streaming(
    ws,
    agent_name: str,
    user_text: str,
    file_context: str | None,
):
    system = {
        "general": "You are a helpful assistant.",
        "summarizer": "You summarize clearly and briefly.",
        "extractor": "You extract key structured facts and list them.",
    }[agent_name]

    context_block = ""
    if file_context:
        context_block = f"\n\nUser uploaded file content:\n{file_context}\n"

    q: asyncio.Queue[str | None] = asyncio.Queue()

    def producer():
        try:
            stream = client.responses.create(
                model="gpt-5-mini",
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_text + context_block},
                ],
                stream=True,
            )
            for event in stream:
                if getattr(event, "type", None) == "response.output_text.delta":
                    delta = event.delta
                    if delta:
                        q.put_nowait(delta)
        finally:
            q.put_nowait(None)

    asyncio.create_task(asyncio.to_thread(producer))

    full = ""
    while True:
        chunk = await q.get()
        if chunk is None:
            break
        full += chunk
        await ws.send_json({"type": "assistant_delta", "delta": chunk})

    await ws.send_json({"type": "assistant_message", "text": full})

@app.get("/")
def root():
    return {"ok": True, "message": "Backend is running"}


@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    user_email = verify_access_token(token)

    file_id = str(uuid.uuid4())
    safe_name = (file.filename or "upload.bin").replace("/", "_")
    dest = UPLOAD_DIR / f"{file_id}__{safe_name}"

    contents = await file.read()
    dest.write_bytes(contents)

    preview = ""
    try:
        preview = contents[:5000].decode("utf-8", errors="ignore")
    except Exception:
        preview = ""

    return {
        "file_id": file_id,
        "filename": safe_name,
        "bytes": len(contents),
        "text_preview": preview,
    }

@app.websocket("/ws/chat")
async def chat(ws: WebSocket):
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=1008)
        return

    try:
        user = verify_token(token)
    except HTTPException:
        await ws.close(code=1008)
        return


    await ws.accept()
    session_state: dict[str, Any] = {"file_preview": None, "user": user_email}


    try:
        while True:
            msg = await ws.receive_json()

            kind = msg.get("type")
            if kind == "set_file":
                session_state["file_preview"] = msg.get("text_preview") or ""
                await ws.send_json({"type": "status", "message": "File attached to chat context."})
                continue

            if kind != "user_message":
                await ws.send_json({"type": "error", "message": "Unknown message type."})
                continue

            user_text = (msg.get("text") or "").strip()
            if not user_text:
                await ws.send_json({"type": "error", "message": "Empty message."})
                continue

            agent = route_agent(user_text)
            await ws.send_json({"type": "status", "message": f"Agent: {agent}"})

            await call_model_streaming(
                ws,
                agent,
                user_text,
                session_state.get("file_preview"),
            )


    except WebSocketDisconnect:
        return
    

class GoogleAuthBody(BaseModel):
    credential: str

@app.post("/api/auth/google")
def auth_google(body: GoogleAuthBody):
    if not GOOGLE_CLIENT_ID:
        print("Missing GOOGLE_CLIENT_ID")
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID not set")
    if not JWT_SECRET:
        print("Missing JWT_SECRET")
        raise HTTPException(status_code=500, detail="JWT_SECRET not set")

    try:
        info = id_token.verify_oauth2_token(
            body.credential,
            grequests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except Exception as e:
        print("Google token verify failed:", repr(e))
        raise HTTPException(status_code=401, detail="Invalid Google token")

    email = (info.get("email") or "").lower()
    email_verified = info.get("email_verified")
    print("Google login:", email, "verified:", email_verified)

    if not email or not email_verified:
        raise HTTPException(status_code=401, detail="Email not verified")

    if ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
        print("Email not allowed:", email, "allowed:", ALLOWED_EMAILS)
        raise HTTPException(status_code=403, detail="Not allowed")

    token = create_access_token(email)
    return {"access_token": token, "token_type": "bearer"}
