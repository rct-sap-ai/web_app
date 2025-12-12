import { API_BASE } from "./app.js";

let sessionToken = localStorage.getItem("sessionToken") || "";

export function isAuthed() {
  return !!sessionToken;
}

export function getSessionToken() {
  return sessionToken;
}

function decodeJwtPayload(token) {
  try {
    const payload = token.split(".")[1];
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

export function getUserEmail() {
  if (!sessionToken) return "";
  const payload = decodeJwtPayload(sessionToken);
  return payload && payload.sub ? payload.sub : "";
}

async function exchangeGoogleCredential(apiBase, credential) {
  const r = await fetch(apiBase + "/api/auth/google", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential }),
  });

  const text = await r.text();
  if (!r.ok) throw new Error(text || ("Auth failed: " + r.status));

  const data = JSON.parse(text);
  sessionToken = data.access_token;
  localStorage.setItem("sessionToken", sessionToken);
}

export function logout() {
  sessionToken = "";
  localStorage.removeItem("sessionToken");
  if (window.google && google.accounts && google.accounts.id) {
    google.accounts.id.disableAutoSelect();
  }
}

export async function initAuth(googleClientId, apiBase, onLoginSuccess) {
  const googleBtnEl = document.getElementById("googleBtn");

  google.accounts.id.initialize({
    client_id: googleClientId,
    callback: async (resp) => {
      try {
        await exchangeGoogleCredential(apiBase, resp.credential);
        onLoginSuccess();
      } catch (e) {
        alert("Login failed");
        console.log(e);
      }
    },
  });

  google.accounts.id.renderButton(googleBtnEl, { theme: "outline", size: "large" });
}
