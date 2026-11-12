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

try {
  apiKeyInput.value = localStorage.getItem("valkiria.apiKey") || "";
} catch (_) { /* almacenamiento no disponible */ }
apiKeyInput.addEventListener("change", () => {
  try { localStorage.setItem("valkiria.apiKey", apiKeyInput.value.trim()); } catch (_) { /* nada */ }
});

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
  const status = data.ticket && data.ticket.status ? ` · estado ${data.ticket.status}` : "";
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

function pollConversation(conversationId) {
  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      const resp = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}`, { headers: headers() });
      if (!resp.ok) return;
      const data = await resp.json();
      renderTicket(data);
      renderApproval(data.approval);
      if (data.approval && data.approval.status !== "pending") {
        stopPolling();
        const verb = data.approval.status === "approved" ? "aprobó" : "no aprobó";
        addMessage("assistant", `Tu manager ${verb} la solicitud.` + (data.approval.note ? ` Observaciones: ${data.approval.note}` : ""));
      }
    } catch (_) { /* reintenta en el siguiente ciclo */ }
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
    if (data.approval && data.approval.status === "pending") pollConversation(data.conversation_id);
  }
}

async function readStream(resp) {
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      let type = "message";
      let payload = "";
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event: ")) type = line.slice(7);
        else if (line.startsWith("data: ")) payload += line.slice(6);
      }
      if (payload) handleEvent(type, JSON.parse(payload));
    }
  }
}

function errorMessage(status) {
  if (status === 401 || status === 403) return "La API pide una clave válida. Escríbela en «API key».";
  if (status === 429) return "Demasiadas solicitudes seguidas. Espera un momento e inténtalo de nuevo.";
  return "No se pudo procesar la solicitud. Inténtalo de nuevo.";
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
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
    if (!resp.ok) {
      addMessage("assistant", errorMessage(resp.status));
      return;
    }
    await readStream(resp);
  } catch (_) {
    addMessage("assistant", "No hay conexión con el servidor.");
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
});

renderAgents();
