const agentList = document.getElementById("agent-list");
const ticketInfo = document.getElementById("ticket-info");
const messages = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");

const AGENTS = [
  "coordinador",
  "clasificador",
  "diagnostico",
  "politicas",
  "ejecucion",
  "conocimiento",
  "seguimiento",
  "escalacion",
];

function renderAgents(results) {
  agentList.innerHTML = "";
  for (const name of AGENTS) {
    const found = results.find((r) => r.role === name);
    const status = found ? found.status : "pending";
    const el = document.createElement("span");
    el.className = `agent ${status}`;
    el.innerHTML = `<span class="dot"></span>${name}`;
    agentList.appendChild(el);
  }
}

function renderTicket(data) {
  if (!data.ticket_id) {
    ticketInfo.textContent = "Sin ticket aún.";
    return;
  }
  ticketInfo.innerHTML =
    `<strong>${data.ticket_id}</strong> · ${data.category || "general"} · ` +
    `prioridad ${data.priority || "media"}` +
    (data.requires_approval ? " · requiere aprobación" : "");
}

function addMessage(role, text) {
  const el = document.createElement("div");
  el.className = `message ${role}`;
  el.textContent = text;
  messages.appendChild(el);
  messages.scrollTop = messages.scrollHeight;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  addMessage("user", text);
  input.value = "";
  try {
    const resp = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const data = await resp.json();
    renderAgents(data.agents || []);
    renderTicket(data);
    addMessage("assistant", data.reply || "Procesado.");
  } catch (err) {
    addMessage("assistant", "Error al procesar la solicitud.");
  }
});
