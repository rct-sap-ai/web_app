let ws = null;
let pendingAssistantBubble = null;
let lastAgentLabel = "";
let statusDotsTimer = null;

let chatEl, inputEl, statusEl, sendBtn;

function wsBaseFromApiBase(apiBase) {
  if (apiBase.startsWith("https://")) return "wss://" + apiBase.slice("https://".length);
  if (apiBase.startsWith("http://")) return "ws://" + apiBase.slice("http://".length);
  throw new Error("Unexpected API base: " + apiBase);
}

function buildWsUrl(apiBase, token) {
  return wsBaseFromApiBase(apiBase) + "/ws/chat?token=" + encodeURIComponent(token);
}

function addBubble(role, text) {
  const row = document.createElement("div");
  row.className = "row " + role;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  row.appendChild(bubble);
  chatEl.appendChild(row);
  chatEl.scrollTop = chatEl.scrollHeight;
  return bubble;
}

function startStatusThinking() {
  if (statusDotsTimer) return;
  let n = 0;
  statusDotsTimer = setInterval(() => {
    n = (n + 1) % 4;
    statusEl.textContent = "Thinking" + ".".repeat(n);
  }, 350);
}

function stopStatusThinking() {
  if (!statusDotsTimer) return;
  clearInterval(statusDotsTimer);
  statusDotsTimer = null;
  if (lastAgentLabel) statusEl.textContent = lastAgentLabel;
}

export function initChat(apiBase) {
  chatEl = document.getElementById("chat");
  inputEl = document.getElementById("input");
  statusEl = document.getElementById("status");
  sendBtn = document.getElementById("send");

  sendBtn.onclick = () => send();

  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  });

  inputEl.addEventListener("input", () => {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 180) + "px";
  });
}

export function connectChatIfNeeded(sessionToken, apiBase) {
  if (!sessionToken) return;
  if (ws && ws.readyState === 1) return;

  const wsUrl = buildWsUrl(apiBase, sessionToken);
  ws = new WebSocket(wsUrl);

  statusEl.textContent = "Connecting...";

  ws.onopen = () => { statusEl.textContent = "Connected"; };
  ws.onclose = () => {
    stopStatusThinking();
    statusEl.textContent = "Disconnected";
  };
  ws.onerror = () => { statusEl.textContent = "Connection error"; };

  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);

    if (msg.type === "assistant_delta") {
      stopStatusThinking();
      if (!pendingAssistantBubble) pendingAssistantBubble = addBubble("assistant", "");
      pendingAssistantBubble.textContent += msg.delta;
      chatEl.scrollTop = chatEl.scrollHeight;
      return;
    }

    if (msg.type === "assistant_message") {
      stopStatusThinking();
      if (!pendingAssistantBubble) pendingAssistantBubble = addBubble("assistant", "");
      pendingAssistantBubble.textContent = msg.text;
      pendingAssistantBubble = null;
      chatEl.scrollTop = chatEl.scrollHeight;
      return;
    }

    if (msg.type === "status") {
      lastAgentLabel = msg.message;
      statusEl.textContent = msg.message;
      return;
    }

    if (msg.type === "error") {
      statusEl.textContent = "Error: " + msg.message;
      return;
    }
  };
}

export function disconnectChat() {
  if (!ws) return;
  try { ws.close(); } catch {}
  ws = null;
}

function send() {
  const text = inputEl.value.trim();
  if (!text) return;
  if (!ws || ws.readyState !== 1) return;

  addBubble("user", text);
  ws.send(JSON.stringify({ type: "user_message", text }));
  startStatusThinking();

  inputEl.value = "";
  inputEl.style.height = "auto";
  inputEl.focus();
}
