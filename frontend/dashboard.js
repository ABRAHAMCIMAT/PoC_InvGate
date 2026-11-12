"use strict";

const $ = (id) => document.getElementById(id);
const fmt = new Intl.NumberFormat("es-MX");
const pct = new Intl.NumberFormat("es-MX", { style: "percent", maximumFractionDigits: 1 });
const usd = new Intl.NumberFormat("es-MX", { style: "currency", currency: "USD", maximumFractionDigits: 4 });

function headers() {
  let key = "";
  try { key = localStorage.getItem("valkiria.apiKey") || ""; } catch (_) { /* nada */ }
  return key ? { Authorization: `Bearer ${key}` } : {};
}

function el(tag, className, text) {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (text !== undefined) n.textContent = text;
  return n;
}

function bars(target, data, format = fmt.format) {
  const box = $(target);
  box.replaceChildren();
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  if (!entries.length) { box.append(el("p", "empty", "Sin datos en este periodo.")); return; }
  const max = Math.max(...entries.map(([, v]) => v)) || 1;
  for (const [name, value] of entries) {
    const row = el("div", "bar");
    const track = el("div", "track");
    const fill = el("div", "fill");
    fill.style.width = `${(value / max) * 100}%`;
    track.append(fill);
    row.append(el("span", "name", name), track, el("span", "num", format(value)));
    row.title = `${name}: ${format(value)}`;
    box.append(row);
  }
}

function facts(target, pairs) {
  const box = $(target);
  box.replaceChildren();
  for (const [k, v] of pairs) box.append(el("dt", "", k), el("dd", "", v));
}

function render(m) {
  const n = m.negocio, r = m.rendimiento, c = m.costos, o = m.orquestacion;
  $("k-conv").textContent = fmt.format(n.conversaciones);
  $("k-tickets").textContent = fmt.format(n.tickets_creados);
  $("k-esc").textContent = pct.format(n.tasa_escalacion);
  $("k-p95").textContent = `${fmt.format(r.chat_ms.p95)} ms`;
  $("k-cost").textContent = usd.format(c.costo_usd);

  bars("by-category", n.por_categoria);
  bars("by-priority", n.por_prioridad);
  const a = n.aprobaciones;
  facts("approvals", [
    ["Solicitadas", fmt.format(a.solicitadas)],
    ["Aprobadas", fmt.format(a.aprobadas)],
    ["Rechazadas", fmt.format(a.rechazadas)],
    ["Pendientes", fmt.format(a.pendientes)],
    ["Espera media", `${fmt.format(Math.round(a.espera_media_s / 60))} min`],
  ]);

  facts("chat-latency", [
    ["Chat p50", `${fmt.format(r.chat_ms.p50)} ms`],
    ["Chat p95", `${fmt.format(r.chat_ms.p95)} ms`],
    ["Chat máximo", `${fmt.format(r.chat_ms.max)} ms`],
    ["Peticiones limitadas (429)", fmt.format(r.peticiones_limitadas)],
  ]);
  bars("agent-latency", Object.fromEntries(Object.entries(r.por_agente_ms).map(([k, v]) => [k, v.p95])),
    (v) => fmt.format(v));

  facts("costs", [
    ["Llamadas al LLM", fmt.format(c.llamadas_llm)],
    ["Tokens de entrada", fmt.format(c.tokens_entrada)],
    ["Tokens de salida", fmt.format(c.tokens_salida)],
    ["Costo por conversación", usd.format(c.costo_por_conversacion_usd)],
  ]);
  const tbody = $("by-model").querySelector("tbody");
  tbody.replaceChildren();
  for (const [model, v] of Object.entries(c.por_modelo)) {
    const tr = el("tr");
    tr.append(el("td", "", model), el("td", "n", fmt.format(v.llamadas)), el("td", "n", fmt.format(v.tokens)),
      el("td", "n", usd.format(v.costo_usd)));
    tbody.append(tr);
  }

  facts("states", [
    ["Correctos", fmt.format(o.estados.ok)],
    ["Con atención", fmt.format(o.estados.warning)],
    ["Con falla", fmt.format(o.estados.error)],
    ["Degradaciones del LLM", fmt.format(o.degradaciones_llm)],
  ]);
  const stacks = $("agent-states");
  stacks.replaceChildren();
  const agents = Object.entries(o.por_agente);
  if (!agents.length) stacks.append(el("p", "empty", "Sin datos en este periodo."));
  for (const [agent, s] of agents) {
    const total = s.ok + s.warning + s.error || 1;
    const row = el("div", "stack-row");
    const stack = el("div", "stack");
    for (const k of ["ok", "warning", "error"]) {
      if (!s[k]) continue;
      const seg = el("div", k);
      seg.style.width = `${(s[k] / total) * 100}%`;
      seg.title = `${k}: ${s[k]}`;
      stack.append(seg);
    }
    row.append(el("span", "name", agent), stack);
    stacks.append(row);
  }
}

async function load() {
  const status = $("status");
  const hours = $("window").value;
  status.className = "status";
  status.textContent = "Cargando…";
  try {
    const resp = await fetch(`/api/metrics${hours ? `?hours=${hours}` : ""}`, { headers: headers() });
    if (!resp.ok) {
      status.className = "status error";
      status.textContent = resp.status === 401 || resp.status === 403
        ? "Se necesita una API key con rol agent o admin (configúrala en el chat)."
        : `No se pudieron cargar las métricas (HTTP ${resp.status}).`;
      return;
    }
    const m = await resp.json();
    render(m);
    status.textContent = m.negocio.conversaciones
      ? `Actualizado ${new Date().toLocaleTimeString("es-MX")}.`
      : "Aún no hay conversaciones en este periodo. Ejecuta scripts/seed_demo_telemetry.py para poblarlo.";
  } catch (_) {
    status.className = "status error";
    status.textContent = "No hay conexión con el servidor.";
  }
}

$("refresh").addEventListener("click", load);
$("window").addEventListener("change", load);
load();
setInterval(load, 30000);
