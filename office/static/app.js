"use strict";

const $ = (id) => document.getElementById(id);

const STRINGS = {
  en: {
    names: { worker: "Developer", reviewer: "Reviewer", user: "You", office: "Office" },
    status: { idle: "free", working: "working", reviewing: "reviewing", approved: "approved", rejected: "sent back" },
    static: {
      connecting: "connecting…",
      cost_title: "Cost estimated by Claude Code; with a subscription it uses your limits, not money",
      scene_label: "Pixel office: the developer and the reviewer at their desks. Click an agent to see its skills.",
      worker_plate: "DEVELOPER",
      reviewer_plate: "REVIEWER",
      open_drawer: "Open skills and activity",
      task_label: "TASK FOR THE DEVELOPER",
      task_placeholder: "For example: build a Python CLI that counts words in a file, with tests",
      btn_task: "Give task",
      btn_review: "Call reviewer",
      btn_rework: "Send back",
      btn_accept: "Accept",
      btn_stop: "Stop",
      autopilot_label: "AUTOPILOT",
      rounds_label: "Max rounds",
      log_title: "LOG",
      log_empty: "All quiet. Give the developer a task.",
      now_title: "NOW",
      skills_title: "SKILLS",
      activity_title: "ACTIVITY",
      close: "Close",
    },
    online: "online",
    offline: "offline",
    hint_working: "The developer is working. You can call the reviewer when they finish.",
    hint_reviewing: "The reviewer is checking the changes…",
    hint_sent: "The fixes are ready. Call the reviewer to check them.",
    hint_rework: "There are review notes: send the work back or adjust the task.",
    hint_approved_notes: "Approved with minor notes. Accept it or send it back.",
    hint_approved: "Approved. Press “Accept” to commit the work to git.",
    hint_started: "The work is ready. Call the reviewer, give a new task, or accept it as is.",
    pilot: {
      off: "Work → review → fixes on its own, until approved or the round limit",
      running: (r, max) => (r ? `Round ${r} of ${max}` : "Running"),
      approved: "Done: approved",
      limit: "Stopped: round limit reached",
      error: "Stopped: an error",
      stopped: "Stopped",
    },
    verdict_sent: "Notes sent to the developer",
    verdict_approved: "Approved",
    verdict_rejected: "Needs work",
    check_failed: (cmd) => `check failed: ${cmd}`,
    serious: (n) => `${n} serious ${n === 1 ? "issue" : "issues"}`,
    non_blocking: (n) => `${n} ${n === 1 ? "note" : "notes"}, none blocking`,
    no_notes: "No notes",
    how_to_fix: "How to fix:",
    in_use: "in use",
    no_skills: "No skills (started with --no-skills)",
    no_activity: "Nothing yet",
    error_status: (code) => `Error ${code}`,
    no_connection: "Cannot reach the server",
    empty_task: "Write what needs to be done",
  },
  ru: {
    names: { worker: "Исполнитель", reviewer: "Ревьюер", user: "Ты", office: "Офис" },
    status: { idle: "свободен", working: "работает", reviewing: "проверяет", approved: "одобрил", rejected: "вернул на доработку" },
    static: {
      connecting: "подключаюсь…",
      cost_title: "Стоимость по оценке Claude Code; с подпиской списываются лимиты, а не деньги",
      scene_label: "Пиксельный офис: исполнитель и ревьюер за своими столами. Нажми на агента, чтобы увидеть его навыки.",
      worker_plate: "ИСПОЛНИТЕЛЬ",
      reviewer_plate: "РЕВЬЮЕР",
      open_drawer: "Открыть навыки и действия",
      task_label: "ЗАДАЧА ДЛЯ ИСПОЛНИТЕЛЯ",
      task_placeholder: "Например: сделай CLI на Python, который считает слова в файле, и напиши к нему тесты",
      btn_task: "Дать задачу",
      btn_review: "Позвать ревьюера",
      btn_rework: "На доработку",
      btn_accept: "Принять",
      btn_stop: "Стоп",
      autopilot_label: "АВТОПИЛОТ",
      rounds_label: "Раундов, не больше",
      log_title: "ЖУРНАЛ",
      log_empty: "Пока тихо. Дай исполнителю задачу.",
      now_title: "СЕЙЧАС",
      skills_title: "НАВЫКИ",
      activity_title: "ДЕЙСТВИЯ",
      close: "Закрыть",
    },
    online: "на связи",
    offline: "нет связи",
    hint_working: "Исполнитель работает. Ревьюера можно позвать, когда он закончит.",
    hint_reviewing: "Ревьюер проверяет изменения…",
    hint_sent: "Исправления готовы. Позови ревьюера, чтобы проверить их.",
    hint_rework: "Есть замечания: отправь на доработку или поправь задачу.",
    hint_approved_notes: "Ревьюер одобрил, но оставил мелкие замечания. Можно принять или отправить на доработку.",
    hint_approved: "Ревьюер одобрил. Нажми «Принять», чтобы зафиксировать работу в git.",
    hint_started: "Работа готова. Позови ревьюера, дай новую задачу или прими как есть.",
    pilot: {
      off: "Работа → ревью → доработка сами, пока не одобрят или не кончатся раунды",
      running: (r, max) => (r ? `Раунд ${r} из ${max}` : "Работает"),
      approved: "Готово: одобрено",
      limit: "Остановлен: лимит раундов",
      error: "Остановлен: ошибка",
      stopped: "Остановлен",
    },
    verdict_sent: "Замечания отправлены исполнителю",
    verdict_approved: "Одобрено",
    verdict_rejected: "Нужна доработка",
    check_failed: (cmd) => `упала проверка ${cmd}`,
    serious: (n) => `${n} ${plural(n, "серьёзное замечание", "серьёзных замечания", "серьёзных замечаний")}`,
    non_blocking: (n) => `${n} ${plural(n, "замечание", "замечания", "замечаний")}, ни одного блокирующего`,
    no_notes: "Замечаний нет",
    how_to_fix: "Как исправить:",
    in_use: "сейчас",
    no_skills: "Навыков нет (запущено с --no-skills)",
    no_activity: "Пока ничего",
    error_status: (code) => `Ошибка ${code}`,
    no_connection: "Нет связи с сервером",
    empty_task: "Напиши, что нужно сделать",
  },
};

const LOG_KEEP = 500;

let state = null;
let lang = "en";
const log = []; // every entry the server sent, for the drawer's per-agent activity
let drawerAgent = null;
let drawerOpener = null;
const S = () => STRINGS[lang];

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

// ---------- language ----------

function applyLanguage(next) {
  lang = next;
  document.documentElement.lang = lang;
  const s = S().static;
  document.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = s[el.dataset.i18n]));
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => (el.placeholder = s[el.dataset.i18nPlaceholder]));
  document.querySelectorAll("[data-i18n-title]").forEach((el) => (el.title = s[el.dataset.i18nTitle]));
  document.querySelectorAll("[data-i18n-label]").forEach((el) => el.setAttribute("aria-label", s[el.dataset.i18nLabel]));
  document.querySelectorAll(".lang-switch button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
  const conn = $("conn");
  if (conn.dataset.state === "online") conn.textContent = S().online;
  else if (conn.dataset.state === "offline") conn.textContent = S().offline;
  document.querySelectorAll(".feed .who").forEach((el) => {
    el.textContent = `${S().names[el.dataset.agent] || el.dataset.agent} · ${el.dataset.time}`;
  });
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
  if (s.lang && s.lang !== lang) applyLanguage(s.lang);
  const t = S();
  $("workspace").textContent = s.workspace;
  $("workspace").title = s.workspace;
  $("cost").textContent = formatCost(s.cost_usd);

  for (const agent of ["worker", "reviewer"]) {
    const a = s.agents[agent];
    $(`desk-${agent}`).dataset.status = a.status;
    setText($(`bubble-${agent}`), a.bubble);
    $(`status-${agent}`).textContent = t.status[a.status] || a.status;
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
  if (working) hint = t.hint_working;
  else if (reviewing) hint = t.hint_reviewing;
  else if (s.verdict?.sent) hint = t.hint_sent;
  else if (needsRework) hint = t.hint_rework;
  else if (s.verdict?.approved && hasIssues) hint = t.hint_approved_notes;
  else if (s.verdict?.approved) hint = t.hint_approved;
  else if (started) hint = t.hint_started;
  $("hint").textContent = hint;

  renderAutopilot(s.autopilot);
  renderVerdict(s.verdict);
  if (drawerAgent) renderDrawer();
  window.OfficeScene?.setState(s);
}

function renderAutopilot(pilot) {
  if (!pilot) return;
  const t = S().pilot;
  const box = $("autopilot");
  const stateName = !pilot.enabled ? "off" : pilot.halted || "running";
  box.dataset.state = stateName;
  $("autopilot-toggle").checked = pilot.enabled;
  $("autopilot-rounds").value = String(pilot.max_rounds);
  $("autopilot-status").textContent =
    stateName === "running" ? t.running(pilot.round, pilot.max_rounds) : t[stateName];
}

function renderVerdict(v) {
  const t = S();
  const box = $("verdict");
  box.hidden = !v;
  if (!v) return;
  box.dataset.approved = String(v.approved);
  box.dataset.sent = String(Boolean(v.sent));
  $("verdict-stamp").textContent = v.approved ? "✓" : "✗";
  $("verdict-title").textContent = v.sent ? t.verdict_sent : v.approved ? t.verdict_approved : t.verdict_rejected;
  const n = v.issues.length;
  const blocking = v.issues.filter((i) => i.severity === "critical" || i.severity === "major").length;
  const reasons = v.checks.filter((c) => !c.passed).map((c) => t.check_failed(c.command));
  if (blocking) reasons.push(t.serious(blocking));
  $("verdict-reasons").textContent = reasons.join(" · ") || (n ? t.non_blocking(n) : t.no_notes);
  $("verdict-summary").textContent = v.summary;

  $("verdict-checks").replaceChildren(...v.checks.map((c) => {
    const li = document.createElement("li");
    li.className = c.passed ? "pass" : "fail";
    li.textContent = `${c.passed ? "✓" : "✗"} ${c.command}`;
    return li;
  }));

  $("verdict-issues").replaceChildren(...v.issues.map((i) => {
    const li = document.createElement("li");
    const head = document.createElement("div");
    head.className = "issue-head";
    const sev = document.createElement("span");
    sev.className = `sev ${i.severity}`;
    sev.textContent = i.severity;
    const title = document.createElement("strong");
    title.textContent = i.title;
    head.append(sev, title);
    if (i.file) {
      const where = document.createElement("span");
      where.className = "issue-where";
      where.textContent = i.line ? `${i.file}:${i.line}` : i.file;
      head.append(where);
    }
    const why = document.createElement("p");
    why.className = "why";
    why.textContent = i.explanation;
    const fix = document.createElement("p");
    fix.className = "fix";
    fix.textContent = `${t.how_to_fix} ${i.suggestion}`;
    li.append(head, why, fix);
    return li;
  }));
}

function logItem(entry) {
  const li = document.createElement("li");
  li.dataset.agent = entry.agent;
  li.dataset.kind = entry.kind;
  const who = document.createElement("span");
  who.className = "who";
  const time = new Date(entry.time * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  who.dataset.agent = entry.agent;
  who.dataset.time = time;
  who.textContent = `${S().names[entry.agent] || entry.agent} · ${time}`;
  const text = document.createElement("span");
  text.className = "text";
  text.textContent = entry.kind === "tool" ? `→ ${entry.text}` : entry.kind === "skill" ? `✦ ${entry.text}` : entry.text;
  li.append(who, text);
  return li;
}

function addLog(entry) {
  log.push(entry);
  if (log.length > LOG_KEEP) log.shift();
  const feed = $("feed");
  const nearBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 40;
  feed.appendChild(logItem(entry));
  $("feed-empty").hidden = true;
  if (nearBottom) feed.scrollTop = feed.scrollHeight;
  if (drawerAgent && entry.agent === drawerAgent) renderDrawerLog();
}

// ---------- drawer ----------

function openDrawer(agent, opener) {
  drawerAgent = agent;
  drawerOpener = opener || document.activeElement;
  const drawer = $("drawer");
  drawer.dataset.agent = agent;
  renderDrawer();
  window.OfficeScene?.drawPortrait($("drawer-portrait"), agent);
  document.body.classList.add("drawer-open");
  drawer.classList.add("open");
  $("drawer-close").focus({ preventScroll: true });
}

function closeDrawer() {
  if (!drawerAgent) return;
  drawerAgent = null;
  $("drawer").classList.remove("open");
  document.body.classList.remove("drawer-open");
  if (drawerOpener && document.contains(drawerOpener)) drawerOpener.focus({ preventScroll: true });
}

function renderDrawer() {
  if (!state || !drawerAgent) return;
  const t = S();
  const agent = state.agents[drawerAgent];
  $("drawer-title").textContent = t.names[drawerAgent];
  $("drawer-status").textContent = t.status[agent.status] || agent.status;
  $("drawer").dataset.status = agent.status;
  $("drawer-bubble").textContent = agent.bubble;

  const skills = state.skills?.[drawerAgent] || [];
  const list = $("drawer-skills");
  if (!skills.length) {
    const li = document.createElement("li");
    li.className = "skill empty";
    li.textContent = t.no_skills;
    list.replaceChildren(li);
  } else {
    list.replaceChildren(...skills.map((skill) => {
      const li = document.createElement("li");
      li.className = "skill";
      li.dataset.active = String(skill.name === agent.skill);
      const name = document.createElement("strong");
      name.textContent = skill.name;
      if (skill.name === agent.skill) {
        const badge = document.createElement("em");
        badge.textContent = t.in_use;
        name.append(" ", badge);
      }
      const about = document.createElement("span");
      about.textContent = skill.label;
      li.append(name, about);
      return li;
    }));
  }
  renderDrawerLog();
}

function renderDrawerLog() {
  const list = $("drawer-log");
  const mine = log.filter((e) => e.agent === drawerAgent).slice(-40);
  if (!mine.length) {
    const li = document.createElement("li");
    li.className = "empty-item";
    li.textContent = S().no_activity;
    list.replaceChildren(li);
    return;
  }
  list.replaceChildren(...mine.map(logItem));
  list.scrollTop = list.scrollHeight;
}

// Keep Tab inside the open drawer.
function trapFocus(e) {
  if (e.key !== "Tab" || !drawerAgent) return;
  const focusable = [...$("drawer").querySelectorAll("button, [href], select, textarea, input, [tabindex]:not([tabindex='-1'])")]
    .filter((el) => !el.disabled && el.offsetParent !== null);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (e.shiftKey && document.activeElement === first) { last.focus(); e.preventDefault(); }
  else if (!e.shiftKey && document.activeElement === last) { first.focus(); e.preventDefault(); }
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
      toast(data.error || S().error_status(res.status));
      return false;
    }
    render(data);
    return true;
  } catch {
    toast(S().no_connection);
    return false;
  }
}

function connect() {
  const conn = $("conn");
  const events = new EventSource("/api/events");
  events.onopen = () => {
    conn.dataset.state = "online";
    conn.textContent = S().online;
    // The server replays the recent log on every (re)connect.
    log.length = 0;
    $("feed").replaceChildren();
    $("feed-empty").hidden = false;
  };
  events.onerror = () => {
    conn.dataset.state = "offline";
    conn.textContent = S().offline;
  };
  events.onmessage = (msg) => {
    const event = JSON.parse(msg.data);
    if (event.type === "state") render(event.state);
    else if (event.type === "log") addLog(event.entry);
  };
}

// ---------- wiring ----------

$("task-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("task-input");
  if (!input.value.trim()) {
    toast(S().empty_task);
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

function sendAutopilot() {
  return post("/api/autopilot", {
    enabled: $("autopilot-toggle").checked,
    max_rounds: Number($("autopilot-rounds").value),
  });
}
$("autopilot-toggle").addEventListener("change", sendAutopilot);
$("autopilot-rounds").addEventListener("change", sendAutopilot);

document.querySelectorAll(".lang-switch button").forEach((button) => {
  button.addEventListener("click", () => {
    // The language is shared with the agents, so the server owns it.
    if (button.dataset.lang !== lang) post("/api/lang", { lang: button.dataset.lang });
  });
});

document.querySelectorAll("[data-drawer]").forEach((button) => {
  button.addEventListener("click", () => openDrawer(button.dataset.drawer, button));
});
window.addEventListener("office:agent-click", (e) => openDrawer(e.detail.agent, $("scene")));
$("drawer-close").addEventListener("click", closeDrawer);
$("drawer-backdrop").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeDrawer();
  trapFocus(e);
});

applyLanguage(lang);
connect();
