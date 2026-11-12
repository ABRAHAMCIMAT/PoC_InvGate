"use strict";

const agentList = document.getElementById("agent-list");
const ticketInfo = document.getElementById("ticket-info");
const approvalInfo = document.getElementById("approval-info");
const messages = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
const sendBtn = document.getElementById("send");
const apiKeyInput = document.getElementById("api-key");

const AGENTS = [
  "coordinador", "clasificador", "diagnostico", "politicas",
  "ejecucion", "conocimiento", "seguimiento", "escalacion",
];
const APPROVAL_LABEL = {
  pending: "Pendiente de aprobación",
  approved: "Aprobada",
  rejected: "Rechazada",
  expired: "Vencida sin respuesta",
};
const POLL_MS = 5000;

let agentState = {};
let pollTimer = null;

const STORAGE_KEY = "valkiria.apiKey";

// El almacenamiento puede no existir (modo privado, cookies bloqueadas): la clave solo no se recuerda.
function readStoredKey() {
  try {
    return localStorage.getItem(STORAGE_KEY) || "";
  } catch (err) {
    console.warn("No se pudo leer la API key guardada:", err);
    return "";
  }
}

function storeKey(value) {
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch (err) {
    console.warn("No se pudo guardar la API key:", err);
  }
}

apiKeyInput.value = readStoredKey();
apiKeyInput.addEventListener("change", () => storeKey(apiKeyInput.value.trim()));

function headers() {
  const h = { "Content-Type": "application/json" };
  const key = apiKeyInput.value.trim();
  if (key) h.Authorization = `Bearer ${key}`;
  return h;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderAgents() {
  agentList.replaceChildren();
  for (const name of AGENTS) {
    const found = agentState[name];
    const status = found ? found.status : "pending";
    const chip = el("span", `agent ${status}`);
    chip.title = found ? found.output : "en espera";
    chip.append(el("span", "dot"), document.createTextNode(name));
    agentList.append(chip);
  }
}

function renderTicket(data) {
  ticketInfo.replaceChildren();
  if (!data.ticket_id) {
    ticketInfo.textContent = data.done ? "No se pudo crear el ticket." : "Sin ticket aún.";
    return;
  }
  const status = data.ticket?.status ? ` · estado ${data.ticket.status}` : "";
  ticketInfo.append(
    el("strong", "", data.ticket_id),
    document.createTextNode(
      ` · ${data.category || "general"} · prioridad ${data.priority || "media"}${status}` +
      (data.escalated ? ` · escalado a Nivel ${data.escalation_level}` : "")
    )
  );
}

function renderApproval(approval) {
  if (!approval) {
    approvalInfo.hidden = true;
    return;
  }
  approvalInfo.hidden = false;
  approvalInfo.className = `approval ${approval.status}`;
  approvalInfo.replaceChildren(el("strong", "", APPROVAL_LABEL[approval.status] || approval.status));
  if (approval.manager_name) {
    approvalInfo.append(document.createTextNode(` · ${approval.manager_name}`));
  }
  if (approval.note) {
    const note = el("p", "note");
    note.append(el("span", "note-label", "Observaciones del manager: "), document.createTextNode(approval.note));
    approvalInfo.append(note);
  } else if (approval.status === "pending") {
    approvalInfo.append(el("p", "note", "Verás aquí la decisión y las observaciones en cuanto el manager responda."));
  }
}

function addMessage(role, text) {
  const node = el("div", `message ${role}`, text);
  messages.append(node);
  messages.scrollTop = messages.scrollHeight;
  return node;
}

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
}

async function pollOnce(conversationId) {
  const resp = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}`, { headers: headers() });
  if (!resp.ok) return;
  const data = await resp.json();
  renderTicket(data);
  renderApproval(data.approval);
  const approval = data.approval;
  if (!approval || approval.status === "pending") return;
  stopPolling();
  const verb = approval.status === "approved" ? "aprobó" : "no aprobó";
  const note = approval.note ? ` Observaciones: ${approval.note}` : "";
  addMessage("assistant", `Tu manager ${verb} la solicitud.${note}`);
}

function pollConversation(conversationId) {
  stopPolling();
  pollTimer = setInterval(() => {
    // Un fallo de red no detiene el sondeo: se reintenta en el siguiente ciclo.
    pollOnce(conversationId).catch((err) => console.warn("Sondeo fallido:", err));
  }, POLL_MS);
}

function handleEvent(type, data) {
  if (type === "agent") {
    agentState[data.role] = data;
    renderAgents();
  } else if (type === "done") {
    renderTicket(data);
    renderApproval(data.approval);
    addMessage("assistant", data.reply || "Procesado.");
    if (data.approval?.status === "pending") pollConversation(data.conversation_id);
  }
}

// Un evento SSE: líneas "event: <tipo>" y "data: <json>" separadas del siguiente por una línea vacía.
function parseSseEvent(chunk) {
  let type = "message";
  let payload = "";
  for (const line of chunk.split("\n")) {
    if (line.startsWith("event: ")) type = line.slice(7);
    else if (line.startsWith("data: ")) payload += line.slice(6);
  }
  return { type, payload };
}

// Procesa los eventos completos del búfer y devuelve lo que queda sin terminar.
function drainEvents(buffer) {
  const parts = buffer.split("\n\n");
  const rest = parts.pop();
  for (const chunk of parts) {
    const { type, payload } = parseSseEvent(chunk);
    if (payload) handleEvent(type, JSON.parse(payload));
  }
  return rest;
}

async function readStream(resp) {
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let chunk = await reader.read();
  while (!chunk.done) {
    buffer = drainEvents(buffer + decoder.decode(chunk.value, { stream: true }));
    chunk = await reader.read();
  }
  drainEvents(buffer + "\n\n");
}

function errorMessage(status) {
  if (status === 401 || status === 403) return "La API pide una clave válida. Escríbela en «API key».";
  if (status === 429) return "Demasiadas solicitudes seguidas. Espera un momento e inténtalo de nuevo.";
  return "No se pudo procesar la solicitud. Inténtalo de nuevo.";
}

async function sendMessage(text) {
  stopPolling();
  agentState = {};
  renderAgents();
  renderApproval(null);
  addMessage("user", text);
  input.value = "";
  sendBtn.disabled = true;
  try {
    const resp = await fetch("/api/chat/stream", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ message: text }),
    });
    if (resp.ok) {
      await readStream(resp);
    } else {
      addMessage("assistant", errorMessage(resp.status));
    }
  } catch (err) {
    console.warn("Error de red en el chat:", err);
    addMessage("assistant", "No hay conexión con el servidor.");
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (text) sendMessage(text).catch((err) => console.error("Fallo inesperado del chat:", err));
});

renderAgents();
