"use strict";

const $ = (id) => document.getElementById(id);
const SVG_NS = "http://www.w3.org/2000/svg";

const NAMES = { worker: "Исполнитель", reviewer: "Ревьюер", user: "Ты" };
const STATUS_TEXT = {
  idle: "свободен",
  working: "работает",
  reviewing: "проверяет",
  approved: "одобрил",
  rejected: "вернул на доработку",
};

let state = null;

function plural(n, one, few, many) {
  const mod10 = n % 10, mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

function formatCost(usd) {
  if (!usd) return "";
  return usd < 0.01 ? "< $0.01" : `≈ $${usd.toFixed(2)}`;
}

// ---------- desk illustrations ----------

function svg(tag, attrs = {}, children = []) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  for (const child of children) el.appendChild(child);
  return el;
}

function screenLines(role) {
  // Worker sees code, reviewer sees a diff. Lines repeat every 6 rows so the scroll loops seamlessly.
  const code = ["#7aa2f7", "#9ece6a", "#e0af68", "#bb9af7", "#c0caf5", "#7dcfff"];
  const diff = ["#3fb950", "#8b949e", "#f85149", "#3fb950", "#8b949e", "#3fb950"];
  const palette = role === "worker" ? code : diff;
  const widths = [64, 42, 80, 30, 56, 70];
  const indents = [0, 8, 8, 16, 8, 0];
  const lines = [];
  for (let i = 0; i < 18; i++) {
    const k = i % 6;
    lines.push(svg("rect", {
      x: 70 + indents[k], y: 20 + i * 8, width: widths[k] * 0.9, height: 3.5, rx: 1.5,
      fill: palette[(k + Math.floor(i / 6)) % palette.length],
    }));
  }
  return svg("g", { class: "screen-lines", "clip-path": `url(#clip-${role})` }, [svg("g", {}, lines)]);
}

function buildDesk(role) {
  const shirt = role === "worker" ? "var(--worker)" : "var(--reviewer)";
  const hair = role === "worker" ? "#2d2a26" : "#7a4a2a";

  const head = svg("g", { class: "head" }, [
    svg("rect", { x: 113, y: 124, width: 14, height: 10, fill: "#d9a77c" }),
    svg("circle", { cx: 103.5, cy: 116, r: 4, fill: "#e8b98f" }),
    svg("circle", { cx: 136.5, cy: 116, r: 4, fill: "#e8b98f" }),
    svg("circle", { cx: 120, cy: 112, r: 16, fill: hair }),
  ]);
  if (role === "worker") {
    // headphones
    head.appendChild(svg("path", { d: "M102 112 a18 18 0 0 1 36 0", fill: "none", stroke: "#1b1d22", "stroke-width": 4, "stroke-linecap": "round" }));
    head.appendChild(svg("rect", { x: 98, y: 108, width: 7, height: 12, rx: 3, fill: "#1b1d22" }));
    head.appendChild(svg("rect", { x: 135, y: 108, width: 7, height: 12, rx: 3, fill: "#1b1d22" }));
  } else {
    // hair bun
    head.appendChild(svg("circle", { cx: 120, cy: 93, r: 7, fill: hair }));
  }

  const extras = role === "worker"
    ? [
        svg("rect", { x: 192, y: 90, width: 13, height: 14, rx: 2, fill: "var(--worker)" }),
        svg("path", { d: "M205 94 h3 a3 3 0 0 1 0 6 h-3", fill: "none", stroke: "var(--worker)", "stroke-width": 2 }),
        svg("path", { class: "steam", d: "M196 86 q-3 -4 0 -8 M201 86 q3 -4 0 -8", fill: "none", stroke: "var(--muted)", "stroke-width": 1.5, "stroke-linecap": "round" }),
      ]
    : [
        svg("rect", { x: 24, y: 95, width: 26, height: 9, rx: 1, fill: "#e9e6df", transform: "rotate(-4 37 99)" }),
        svg("rect", { x: 26, y: 91, width: 26, height: 9, rx: 1, fill: "#f6f3ec", transform: "rotate(3 39 95)" }),
        svg("rect", { x: 192, y: 92, width: 10, height: 12, rx: 2, fill: "var(--reviewer)" }),
      ];

  const screenOverlays = [screenLines(role)];
  if (role === "reviewer") {
    screenOverlays.push(svg("g", { class: "lens" }, [
      svg("circle", { cx: 84, cy: 32, r: 9, fill: "#ffffff22", stroke: "#fff", "stroke-width": 2 }),
      svg("path", { d: "M91 39 l7 7", stroke: "#fff", "stroke-width": 3, "stroke-linecap": "round" }),
    ]));
    screenOverlays.push(svg("g", { class: "screen-stamp stamp-ok" }, [
      svg("circle", { cx: 120, cy: 49, r: 20, fill: "var(--ok)" }),
      svg("path", { d: "M110 49 l7 7 l13 -14", fill: "none", stroke: "#fff", "stroke-width": 5, "stroke-linecap": "round", "stroke-linejoin": "round" }),
    ]));
    screenOverlays.push(svg("g", { class: "screen-stamp stamp-bad" }, [
      svg("circle", { cx: 120, cy: 49, r: 20, fill: "var(--bad)" }),
      svg("path", { d: "M112 41 l16 16 M128 41 l-16 16", stroke: "#fff", "stroke-width": 5, "stroke-linecap": "round" }),
    ]));
  }

  return svg("svg", { viewBox: "0 0 240 190", role: "img", "aria-label": NAMES[role] }, [
    svg("defs", {}, [
      svg("clipPath", { id: `clip-${role}` }, [svg("rect", { x: 64, y: 14, width: 112, height: 70, rx: 3 })]),
    ]),
    // monitor
    svg("rect", { x: 58, y: 8, width: 124, height: 82, rx: 7, fill: "#2b2f38" }),
    svg("rect", { x: 64, y: 14, width: 112, height: 70, rx: 3, fill: "#0f131a" }),
    ...screenOverlays,
    svg("rect", { x: 112, y: 90, width: 16, height: 12, fill: "#3a3f4a" }),
    svg("rect", { x: 98, y: 99, width: 44, height: 5, rx: 2, fill: "#3a3f4a" }),
    // desk
    svg("rect", { x: 6, y: 104, width: 228, height: 10, rx: 3, style: "fill: var(--desk-top)" }),
    svg("rect", { x: 14, y: 114, width: 212, height: 70, style: "fill: var(--desk)" }),
    svg("rect", { x: 92, y: 100, width: 56, height: 5, rx: 1.5, fill: "#c9ccd3" }),
    ...extras,
    // person, seen from behind
    svg("path", { class: "arm arm-l", d: "M95 136 L104 104", stroke: shirt, "stroke-width": 9, "stroke-linecap": "round" }),
    svg("path", { class: "arm arm-r", d: "M145 136 L136 104", stroke: shirt, "stroke-width": 9, "stroke-linecap": "round" }),
    svg("rect", { x: 86, y: 124, width: 68, height: 62, rx: 26, fill: shirt }),
    head,
    // chair back
    svg("rect", { x: 93, y: 150, width: 54, height: 40, rx: 9, fill: "#3b3f4a" }),
  ]);
}

document.querySelectorAll(".desk-art").forEach((el) => el.appendChild(buildDesk(el.dataset.role)));

// ---------- rendering ----------

function setText(el, text) {
  if (el.textContent !== text) {
    el.textContent = text;
    el.classList.remove("pop");
    void el.offsetWidth; // restart the animation
    el.classList.add("pop");
  }
}

function render(s) {
  state = s;
  $("workspace").textContent = s.workspace;
  $("workspace").title = s.workspace;
  $("cost").textContent = formatCost(s.cost_usd);

  for (const agent of ["worker", "reviewer"]) {
    const a = s.agents[agent];
    $(`desk-${agent}`).dataset.status = a.status;
    setText($(`bubble-${agent}`), a.bubble);
    $(`status-${agent}`).textContent = STATUS_TEXT[a.status] || a.status;
  }

  const working = s.agents.worker.status === "working";
  const reviewing = s.agents.reviewer.status === "reviewing";
  const busy = working || reviewing;
  const started = s.task !== null;
  const fresh = Boolean(s.verdict && !s.verdict.sent);
  const needsRework = fresh && !s.verdict.approved;
  const hasIssues = fresh && s.verdict.issues.length > 0;

  $("btn-task").disabled = busy;
  $("btn-review").disabled = busy || !started;
  $("btn-rework").disabled = busy || !(needsRework || hasIssues);
  $("btn-accept").disabled = busy || !started;
  $("btn-stop").disabled = !working;

  let hint = "";
  if (working) hint = "Исполнитель работает. Ревьюера можно позвать, когда он закончит.";
  else if (reviewing) hint = "Ревьюер проверяет изменения…";
  else if (s.verdict?.sent) hint = "Исправления готовы. Позови ревьюера, чтобы проверить их.";
  else if (needsRework) hint = "Есть замечания: отправь на доработку или поправь задачу.";
  else if (s.verdict?.approved && hasIssues) hint = "Ревьюер одобрил, но оставил мелкие замечания. Можно принять или отправить на доработку.";
  else if (s.verdict?.approved) hint = "Ревьюер одобрил. Нажми «Принять», чтобы зафиксировать работу в git.";
  else if (started) hint = "Работа готова. Позови ревьюера, дай новую задачу или прими как есть.";
  $("hint").textContent = hint;

  renderVerdict(s.verdict);
}

function renderVerdict(v) {
  const box = $("verdict");
  box.hidden = !v;
  if (!v) return;
  box.dataset.approved = String(v.approved);
  box.dataset.sent = String(Boolean(v.sent));
  $("verdict-stamp").textContent = v.approved ? "✓" : "✗";
  $("verdict-title").textContent = v.sent
    ? "Замечания отправлены исполнителю"
    : v.approved ? "Одобрено" : "Нужна доработка";
  const n = v.issues.length;
  const blocking = v.issues.filter((i) => i.severity === "critical" || i.severity === "major").length;
  const reasons = v.checks.filter((c) => !c.passed).map((c) => `упала проверка ${c.command}`);
  if (blocking) reasons.push(`${blocking} ${plural(blocking, "серьёзное замечание", "серьёзных замечания", "серьёзных замечаний")}`);
  $("verdict-reasons").textContent = reasons.join(" · ")
    || (n ? `${n} ${plural(n, "замечание", "замечания", "замечаний")}, ни одного блокирующего` : "Замечаний нет");
  $("verdict-summary").textContent = v.summary;

  const checks = $("verdict-checks");
  checks.replaceChildren(...v.checks.map((c) => {
    const li = document.createElement("li");
    li.className = c.passed ? "pass" : "fail";
    li.textContent = `${c.passed ? "✓" : "✗"} ${c.command}`;
    return li;
  }));

  const issues = $("verdict-issues");
  issues.replaceChildren(...v.issues.map((i) => {
    const li = document.createElement("li");
    const head = document.createElement("div");
    head.className = "issue-head";
    const sev = document.createElement("span");
    sev.className = `sev ${i.severity}`;
    sev.textContent = i.severity;
    const title = document.createElement("strong");
    title.textContent = i.title;
    const where = document.createElement("span");
    where.className = "issue-where";
    where.textContent = i.line ? `${i.file}:${i.line}` : i.file;
    head.append(sev, title, where);
    const why = document.createElement("p");
    why.textContent = i.explanation;
    const fix = document.createElement("p");
    fix.className = "fix";
    fix.textContent = `Как исправить: ${i.suggestion}`;
    li.append(head, why, fix);
    return li;
  }));
}

function addLog(entry) {
  const feed = $("feed");
  const nearBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 40;
  const li = document.createElement("li");
  li.dataset.agent = entry.agent;
  li.dataset.kind = entry.kind;
  const who = document.createElement("span");
  who.className = "who";
  const time = new Date(entry.time * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  who.textContent = `${NAMES[entry.agent] || entry.agent} · ${time}`;
  const text = document.createElement("span");
  text.className = "text";
  text.textContent = entry.kind === "tool" ? `→ ${entry.text}` : entry.text;
  li.append(who, text);
  feed.appendChild(li);
  $("feed-empty").hidden = true;
  if (nearBottom) feed.scrollTop = feed.scrollHeight;
}

// ---------- server ----------

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (el.hidden = true), 4000);
}

async function post(path, body = {}) {
  try {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      toast(data.error || `Ошибка ${res.status}`);
      return false;
    }
    render(data);
    return true;
  } catch {
    toast("Нет связи с сервером");
    return false;
  }
}

function connect() {
  const conn = $("conn");
  const events = new EventSource("/api/events");
  events.onopen = () => {
    conn.dataset.state = "online";
    conn.textContent = "на связи";
    // The server replays the recent log on every (re)connect.
    $("feed").replaceChildren();
    $("feed-empty").hidden = false;
  };
  events.onerror = () => {
    conn.dataset.state = "offline";
    conn.textContent = "нет связи";
  };
  events.onmessage = (msg) => {
    const event = JSON.parse(msg.data);
    if (event.type === "state") render(event.state);
    else if (event.type === "log") addLog(event.entry);
  };
}

$("task-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("task-input");
  if (!input.value.trim()) {
    toast("Напиши, что нужно сделать");
    input.focus();
    return;
  }
  if (await post("/api/task", { text: input.value })) input.value = "";
});
$("task-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) $("task-form").requestSubmit();
});
$("btn-review").addEventListener("click", () => post("/api/review"));
$("btn-rework").addEventListener("click", () => post("/api/rework"));
$("btn-accept").addEventListener("click", () => post("/api/accept"));
$("btn-stop").addEventListener("click", () => post("/api/stop"));

connect();
