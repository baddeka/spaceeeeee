"use strict";

const $ = (id) => document.getElementById(id);

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
  window.OfficeScene?.setState(s);
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
