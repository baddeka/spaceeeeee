"use strict";

const $ = (id) => document.getElementById(id);

const STRINGS = {
  en: {
    names: { worker: "coderen", reviewer: "checkren", ideator: "idearen", user: "You", office: "Office" },
    roles: { worker: "Developer", reviewer: "Reviewer", ideator: "Idea maker" },
    status: {
      idle: "resting", working: "working", reviewing: "reviewing", approved: "approved", rejected: "has notes",
      thinking: "thinking", ready: "ideas ready", sleeping: "sleeping",
    },
    static: {
      connecting: "connecting…",
      cost_title: "Cost estimated by Claude Code; with a subscription it uses your limits, not money",
      limits_label: "Subscription limits",
      scene_label: "Pixel office: coderen, checkren and idearen at their desks. Click an agent to see its skills.",
      worker_plate: "coderen",
      reviewer_plate: "checkren",
      ideator_plate: "idearen",
      topic_label: "TOPIC FOR IDEAREN",
      topic_placeholder: "For example: tools for students before exams",
      btn_ideas: "Get ideas",
      open_drawer: "Open skills and activity",
      task_label: "TASK FOR CODEREN",
      task_placeholder: "For example: build a Python CLI that counts words in a file, with tests",
      btn_task: "Give task",
      btn_review: "Call checkren",
      btn_rework: "Send back",
      btn_accept: "Accept",
      btn_stop: "Stop",
      autopilot_label: "AUTOPILOT",
      rounds_label: "Max rounds",
      log_title: "LOG",
      log_empty: "All quiet. Give coderen a task.",
      now_title: "NOW",
      model_title: "MODEL AND EFFORT",
      model_label: "Model",
      effort_label: "Effort",
      choice_note: "Applies from the agent's next run and stays after a restart.",
      skills_title: "SKILLS",
      activity_title: "ACTIVITY",
      close: "Close",
      time_label: "Time of day in the office",
      time_auto: "AUTO",
      time_day: "DAY",
      time_night: "NIGHT",
      time_auto_title: "Follow your clock",
    },
    online: "online",
    offline: "offline",
    hint_working: "coderen is working. You can call checkren when the work is ready.",
    hint_reviewing: "checkren is checking the changes…",
    hint_sent: "The fixes are ready. Call checkren to check them.",
    hint_rework: "There are review notes: send the work back or adjust the task.",
    hint_approved_notes: "Approved with minor notes. Accept it or send it back.",
    hint_approved: "Approved. Press “Accept” to commit the work to git.",
    hint_started: "The work is ready. Call checkren, give a new task, or accept it as is.",
    pilot: {
      off: "Work → review → fixes on its own, until approved or the round limit",
      running: (r, max) => (r ? `Round ${r} of ${max}` : "Running"),
      approved: "Done: approved",
      limit: "Stopped: round limit reached",
      error: "Stopped: an error",
      stopped: "Stopped",
    },
    verdict_sent: "Notes sent to coderen",
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
    empty_topic: "Write a topic for the ideas",
    ideas_for: (topic) => `Ideas on “${topic}”`,
    recommended: "recommended",
    scope: { small: "small", medium: "medium", large: "large" },
    brief: "Brief for coderen",
    hand_off: "Give to coderen",
    handed: "With coderen",
    limits: { five_hour: "5h", seven_day: "week", seven_day_opus: "week · Opus", seven_day_sonnet: "week · Sonnet" },
    limits_none: "limits —",
    limits_checking: "limits…",
    limits_none_title: "Click to check your subscription limits: one tiny request to Haiku",
    limit_title: (name, pct, when) => `${name}: ${pct}% used, resets ${when}. Click to check again.`,
    models: {
      haiku: "Haiku · fast and cheap",
      sonnet: "Sonnet · balanced",
      opus: "Opus · strong",
      fable: "Fable · strongest, may need usage credits",
    },
    auto_from: (value) => `auto (${value})`,
    auto_claude_code: "auto (Claude Code's default)",
    auto_review_effort: "auto (the project's, else high)",
  },
  ru: {
    names: { worker: "coderen", reviewer: "checkren", ideator: "idearen", user: "Ты", office: "Офис" },
    roles: { worker: "Исполнитель", reviewer: "Ревьюер", ideator: "Генератор идей" },
    // Present tense and impersonal forms, so no status guesses anyone's gender.
    status: {
      idle: "отдыхает", working: "работает", reviewing: "проверяет", approved: "одобрено", rejected: "есть замечания",
      thinking: "думает", ready: "идеи готовы", sleeping: "спит",
    },
    static: {
      connecting: "подключаюсь…",
      cost_title: "Стоимость по оценке Claude Code; с подпиской списываются лимиты, а не деньги",
      limits_label: "Лимиты подписки",
      scene_label: "Пиксельный офис: coderen, checkren и idearen за своими столами. Нажми на агента, чтобы увидеть его навыки.",
      worker_plate: "coderen",
      reviewer_plate: "checkren",
      ideator_plate: "idearen",
      topic_label: "ТЕМА ДЛЯ IDEAREN",
      topic_placeholder: "Например: инструменты для студентов перед сессией",
      btn_ideas: "Придумать идеи",
      open_drawer: "Открыть навыки и действия",
      task_label: "ЗАДАЧА ДЛЯ CODEREN",
      task_placeholder: "Например: сделай CLI на Python, который считает слова в файле, и напиши к нему тесты",
      btn_task: "Дать задачу",
      btn_review: "Позвать checkren",
      btn_rework: "На доработку",
      btn_accept: "Принять",
      btn_stop: "Стоп",
      autopilot_label: "АВТОПИЛОТ",
      rounds_label: "Раундов, не больше",
      log_title: "ЖУРНАЛ",
      log_empty: "Пока тихо. Дай coderen задачу.",
      now_title: "СЕЙЧАС",
      model_title: "МОДЕЛЬ И EFFORT",
      model_label: "Модель",
      effort_label: "Effort",
      choice_note: "Действует со следующего запуска агента и сохраняется после перезапуска.",
      skills_title: "НАВЫКИ",
      activity_title: "ДЕЙСТВИЯ",
      close: "Закрыть",
      time_label: "Время суток в офисе",
      time_auto: "АВТО",
      time_day: "ДЕНЬ",
      time_night: "НОЧЬ",
      time_auto_title: "По твоим часам",
    },
    online: "на связи",
    offline: "нет связи",
    hint_working: "coderen работает. checkren можно позвать, когда работа будет готова.",
    hint_reviewing: "checkren проверяет изменения…",
    hint_sent: "Исправления готовы. Позови checkren, чтобы проверить их.",
    hint_rework: "Есть замечания: отправь на доработку или поправь задачу.",
    hint_approved_notes: "Работа одобрена, но есть мелкие замечания. Можно принять или отправить на доработку.",
    hint_approved: "Работа одобрена. Нажми «Принять», чтобы зафиксировать её в git.",
    hint_started: "Работа готова. Позови checkren, дай новую задачу или прими как есть.",
    pilot: {
      off: "Работа → ревью → доработка сами, пока не одобрят или не кончатся раунды",
      running: (r, max) => (r ? `Раунд ${r} из ${max}` : "Работает"),
      approved: "Готово: одобрено",
      limit: "Стоп: лимит раундов",
      error: "Стоп: ошибка",
      stopped: "Остановлено",
    },
    verdict_sent: "Замечания отправлены coderen",
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
    empty_topic: "Напиши тему для идей",
    ideas_for: (topic) => `Идеи по теме «${topic}»`,
    recommended: "рекомендую",
    scope: { small: "небольшая", medium: "средняя", large: "большая" },
    brief: "ТЗ для coderen",
    hand_off: "Передать coderen",
    handed: "У coderen",
    limits: { five_hour: "5 ч", seven_day: "неделя", seven_day_opus: "неделя · Opus", seven_day_sonnet: "неделя · Sonnet" },
    limits_none: "лимиты —",
    limits_checking: "лимиты…",
    limits_none_title: "Нажми, чтобы проверить лимиты подписки: один крошечный запрос к Haiku",
    limit_title: (name, pct, when) => `${name}: использовано ${pct}%, сброс ${when}. Нажми, чтобы проверить снова.`,
    models: {
      haiku: "Haiku · быстрая и дешёвая",
      sonnet: "Sonnet · золотая середина",
      opus: "Opus · сильная",
      fable: "Fable · самая сильная, может требовать кредиты",
    },
    auto_from: (value) => `авто (${value})`,
    auto_claude_code: "авто (как в Claude Code)",
    auto_review_effort: "авто (из проекта или high)",
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
  if (drawerAgent) renderDrawerLog();
}

// ---------- rendering ----------

// Agents write code between backticks; show it in the code font instead of as raw backticks.
// Built from text nodes, never innerHTML, so nothing an agent writes can become markup.
function richText(el, text) {
  const parts = String(text ?? "").split(/`([^`\n]+)`/);
  el.replaceChildren(...parts.map((part, i) => {
    if (i % 2 === 0) return document.createTextNode(part);
    const code = document.createElement("code");
    code.textContent = part;
    return code;
  }));
}

// An agent with nothing to do is resting, or asleep at night; the scene knows which.
function statusText(agent, status) {
  const t = S();
  if (status === "idle" && window.OfficeScene?.restOf(agent) === "sleep") return t.status.sleeping;
  return t.status[status] || status;
}

function renderPlates() {
  if (!state) return;
  for (const agent of ["worker", "reviewer", "ideator"]) {
    if (state.agents[agent]) $(`status-${agent}`).textContent = statusText(agent, state.agents[agent].status);
  }
  if (drawerAgent) renderDrawer();
}

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
  renderLimits(s.limits, s.limits_checking);

  for (const agent of ["worker", "reviewer", "ideator"]) {
    const a = s.agents[agent];
    if (!a) continue;
    $(`desk-${agent}`).dataset.status = a.status;
    setText($(`bubble-${agent}`), a.bubble.replace(/`/g, ""));
    $(`status-${agent}`).textContent = statusText(agent, a.status);
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
  renderIdeas(s, busy);
  renderVerdict(s.verdict);
  if (drawerAgent) renderDrawer();
  window.OfficeScene?.setState(s);
}

// The subscription's usage, as Claude Code reports it: a small bar per limit window.
function renderLimits(limits, checking) {
  const t = S();
  const box = $("limits");
  box.setAttribute("aria-busy", String(Boolean(checking)));
  if (!limits?.length) {
    box.textContent = checking ? t.limits_checking : t.limits_none;
    box.title = t.limits_none_title;
    return;
  }
  box.title = "";
  box.replaceChildren(...limits.map((w) => {
    const pct = Math.round(w.used * 100);
    const name = t.limits[w.name] || w.name;
    const item = document.createElement("span");
    item.className = "limit";
    item.dataset.level = w.status === "rejected" || pct >= 90 ? "high" : w.status === "allowed_warning" || pct >= 70 ? "warn" : "ok";
    const when = w.resets_at
      ? new Date(w.resets_at * 1000).toLocaleString(lang, { weekday: "short", hour: "2-digit", minute: "2-digit" })
      : "—";
    item.title = t.limit_title(name, pct, when);
    const label = document.createElement("span");
    label.textContent = name;
    const bar = document.createElement("span");
    bar.className = "bar";
    const fill = document.createElement("span");
    fill.style.width = `${Math.min(100, Math.max(0, pct))}%`;
    bar.append(fill);
    const value = document.createElement("span");
    value.textContent = `${pct}%`;
    item.append(label, bar, value);
    return item;
  }));
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

let ideasKey = "";

function renderIdeas(s, busy) {
  const t = S();
  const thinking = s.agents.ideator?.status === "thinking";
  $("btn-ideas").disabled = thinking;
  $("btn-ideas-stop").disabled = !thinking;
  $("ideas-topic").textContent = s.ideas && s.topic ? t.ideas_for(s.topic) : "";

  const list = $("idea-cards");
  // Rebuild only when the ideas change, so open briefs stay open between updates.
  const key = JSON.stringify([lang, s.ideas]);
  if (key !== ideasKey) {
    const titles = (ideas) => (ideas || []).map((i) => i.title).join("\n");
    const sameIdeas = ideasKey && titles(JSON.parse(ideasKey)[1]) === titles(s.ideas);
    const open = sameIdeas ? [...list.querySelectorAll("details")].map((d) => d.open) : [];
    ideasKey = key;
    list.replaceChildren(...(s.ideas || []).map((idea, index) => ideaCard(idea, index, t)));
    // A handed-off idea changes the list, but the briefs someone opened stay open.
    list.querySelectorAll("details").forEach((d, i) => (d.open = Boolean(open[i])));
  }
  list.querySelectorAll(".idea-handoff").forEach((button) => {
    const idea = s.ideas[Number(button.dataset.index)];
    button.disabled = busy || idea.handed;
  });
}

function ideaCard(idea, index, t) {
  const li = document.createElement("li");
  li.className = "idea";
  li.dataset.recommended = String(idea.recommended);
  li.dataset.handed = String(idea.handed);

  const head = document.createElement("div");
  head.className = "idea-head";
  const title = document.createElement("strong");
  title.textContent = idea.title;
  const scope = document.createElement("span");
  scope.className = `scope ${idea.scope}`;
  scope.textContent = t.scope[idea.scope] || idea.scope;
  head.append(title, scope);
  if (idea.recommended) {
    const star = document.createElement("span");
    star.className = "star";
    star.textContent = `★ ${t.recommended}`;
    head.append(star);
  }

  const pitch = document.createElement("p");
  richText(pitch, idea.pitch);
  const why = document.createElement("p");
  why.className = "why";
  richText(why, idea.why);

  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = t.brief;
  const brief = document.createElement("div");
  brief.className = "brief";
  richText(brief, idea.task);
  details.append(summary, brief);

  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn primary idea-handoff";
  button.dataset.index = String(index);
  button.textContent = idea.handed ? `✓ ${t.handed}` : t.hand_off;

  li.append(head, pitch, why, details, button);
  return li;
}

let verdictKey = "";

function renderVerdict(v) {
  // Rebuild only when the verdict changes, so text someone is selecting stays selected.
  const key = JSON.stringify([lang, v]);
  if (key === verdictKey) return;
  verdictKey = key;
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
  richText($("verdict-summary"), v.summary);

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
    richText(title, i.title);
    head.append(sev, title);
    if (i.file) {
      const where = document.createElement("span");
      where.className = "issue-where";
      where.textContent = i.line ? `${i.file}:${i.line}` : i.file;
      head.append(where);
    }
    const why = document.createElement("p");
    why.className = "why";
    richText(why, i.explanation);
    const fix = document.createElement("p");
    fix.className = "fix";
    richText(fix, `${t.how_to_fix} ${i.suggestion}`);
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
  if (entry.kind === "tool") text.textContent = `→ ${entry.text}`;
  else if (entry.kind === "skill") text.textContent = `✦ ${entry.text}`;
  else richText(text, entry.text);
  li.append(who, text);
  return li;
}

function addLog(entry) {
  log.push(entry);
  if (log.length > LOG_KEEP) log.shift();
  const feed = $("feed");
  const nearBottom = feed.scrollHeight - feed.scrollTop - feed.clientHeight < 40;
  feed.appendChild(logItem(entry));
  if (feed.children.length > LOG_KEEP) feed.firstElementChild.remove();
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
  renderDrawerLog();
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
  $("drawer-status").textContent = `${t.roles[drawerAgent]} · ${statusText(drawerAgent, agent.status)}`;
  $("drawer").dataset.status = agent.status;
  richText($("drawer-bubble"), agent.bubble);

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
  renderChoices();
}

let choicesKey = "";

// The agent's model and effort. Rebuilt only when they change, so an open list stays open.
function renderChoices() {
  const key = JSON.stringify([lang, drawerAgent, state.choices[drawerAgent], state.defaults]);
  if (key === choicesKey) return;
  choicesKey = key;
  const t = S();
  const choice = state.choices[drawerAgent];
  const { model, effort } = state.defaults;
  const autoEffort = drawerAgent === "reviewer" ? t.auto_review_effort : t.auto_claude_code;
  fillSelect($("drawer-model"), model ? t.auto_from(model) : t.auto_claude_code,
    state.model_choices.map((m) => [m, t.models[m] || m]), choice.model);
  fillSelect($("drawer-effort"), effort ? t.auto_from(effort) : autoEffort,
    state.effort_choices.map((e) => [e, e]), choice.effort);
}

function fillSelect(select, autoLabel, options, value) {
  select.replaceChildren(...[["", autoLabel], ...options].map(([optionValue, label]) => {
    const option = document.createElement("option");
    option.value = optionValue;
    option.textContent = label;
    return option;
  }));
  select.value = value || "";
}

async function sendChoice() {
  const sent = await post("/api/choice", {
    agent: drawerAgent,
    model: $("drawer-model").value,
    effort: $("drawer-effort").value,
  });
  if (!sent && drawerAgent) {
    // Show what the server still has instead of the choice it refused.
    choicesKey = "";
    renderDrawer();
  }
}

// The agent's own activity; rebuilt only when it gets a new entry, not on every state update.
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
    if (res.ok) {
      render(data);
      return true;
    }
    toast(data.error || S().error_status(res.status));
  } catch {
    toast(S().no_connection);
  }
  // Put back what the server still has, so a switch the user flipped does not claim it took effect.
  if (state) render(state);
  return false;
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
    if (drawerAgent) renderDrawerLog();
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
$("btn-stop").addEventListener("click", () => post("/api/stop", { agent: "worker" }));
$("limits").addEventListener("click", () => post("/api/limits"));

$("ideas-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = $("topic-input");
  if (!input.value.trim()) {
    toast(S().empty_topic);
    input.focus();
    return;
  }
  post("/api/ideas", { topic: input.value });
});
$("btn-ideas-stop").addEventListener("click", () => post("/api/stop", { agent: "ideator" }));
$("idea-cards").addEventListener("click", (e) => {
  const button = e.target.closest(".idea-handoff");
  if (button && !button.disabled) post("/api/handoff", { index: Number(button.dataset.index) });
});

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
$("drawer-model").addEventListener("change", sendChoice);
$("drawer-effort").addEventListener("change", sendChoice);
$("drawer-backdrop").addEventListener("click", closeDrawer);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeDrawer();
  trapFocus(e);
});

// ---------- time of day ----------

const TIME_KEY = "ai-office-time";

function setTimeMode(mode) {
  document.querySelectorAll(".time-switch button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.time === mode)));
  window.OfficeScene?.setTimeMode(mode);
  try {
    localStorage.setItem(TIME_KEY, mode);
  } catch {
    // storage can be unavailable (private mode); the switch still works for this visit
  }
}

document.querySelectorAll(".time-switch button").forEach((button) => {
  button.addEventListener("click", () => setTimeMode(button.dataset.time));
});
window.addEventListener("office:rest", renderPlates);

let savedTime = "auto";
try {
  savedTime = localStorage.getItem(TIME_KEY) || "auto";
} catch {
  // keep "auto"
}

applyLanguage(lang);
setTimeMode(savedTime);
connect();
