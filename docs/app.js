import { initAuth, isAuthed, getSessionToken, getUserEmail, logout } from "./auth.js";
import { initChat, connectChatIfNeeded, disconnectChat } from "./chat.js";
import { initUpload } from "./upload.js";

const IS_LOCAL = location.hostname === "localhost" || location.hostname === "127.0.0.1";

export const API_BASE = IS_LOCAL
  ? "http://127.0.0.1:8000"
  : "https://YOUR_RENDER_SERVICE.onrender.com";

export const GOOGLE_CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com";

const pageLanding = document.getElementById("pageLanding");
const pageChat = document.getElementById("pageChat");
const pageUpload = document.getElementById("pageUpload");

const navChat = document.getElementById("navChat");
const navUpload = document.getElementById("navUpload");
const logoutBtn = document.getElementById("logoutBtn");
const topUser = document.getElementById("topUser");
const landingStatus = document.getElementById("landingStatus");

function setAuthUi() {
  const authed = isAuthed();
  navChat.style.display = authed ? "inline-block" : "none";
  navUpload.style.display = authed ? "inline-block" : "none";
  logoutBtn.style.display = authed ? "inline-block" : "none";

  topUser.textContent = authed ? getUserEmail() : "";
  landingStatus.textContent = authed ? "You are signed in." : "Not signed in.";
}

function showOnly(which) {
  pageLanding.style.display = which === "landing" ? "block" : "none";
  pageChat.style.display = which === "chat" ? "block" : "none";
  pageUpload.style.display = which === "upload" ? "block" : "none";
}

function route() {
  const raw = location.hash || "#/landing";
  const path = raw.replace("#", "");

  setAuthUi();

  if (path === "/chat") {
    if (!isAuthed()) {
      location.hash = "#/landing";
      return;
    }
    showOnly("chat");
    connectChatIfNeeded(getSessionToken(), API_BASE);
    return;
  }

  if (path === "/upload") {
    if (!isAuthed()) {
      location.hash = "#/landing";
      return;
    }
    showOnly("upload");
    disconnectChat();
    return;
  }

  showOnly("landing");
  disconnectChat();
}

logoutBtn.onclick = () => {
  logout();
  setAuthUi();
  location.hash = "#/landing";
};

window.addEventListener("hashchange", route);

async function main() {
  initChat(API_BASE);
  initUpload(API_BASE);
  await initAuth(GOOGLE_CLIENT_ID, API_BASE, () => {
    setAuthUi();
    location.hash = "#/chat";
  });
  setAuthUi();
  route();
}

main();
