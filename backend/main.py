import os
import uuid
from pathlib import Path
from typing import Any
import asyncio

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

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




@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
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
    await ws.accept()
    session_state: dict[str, Any] = {"file_preview": None}

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