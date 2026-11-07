"use strict";

const $ = (id) => document.getElementById(id);

const STRINGS = {
  en: {
    names: { backend: "backren", frontend: "frontren", reviewer: "checkren", ideator: "idearen", user: "You", office: "Office" },
    roles: { backend: "Backend developer", frontend: "Frontend developer", reviewer: "Reviewer", ideator: "Idea maker" },
    status: {
      idle: "resting", working: "working", reviewing: "reviewing", approved: "approved", rejected: "has notes",
      thinking: "thinking", ready: "ideas ready", sleeping: "sleeping",
    },
    static: {
      connecting: "connecting…",
      cost_title: "Cost estimated by Claude Code; with a subscription it uses your limits, not money",
      limits_label: "Subscription limits",
      scene_label: "Pixel office: backren and checkren at the back, frontren and idearen in front. Click an agent to see its skills.",
      topic_label: "TOPIC FOR IDEAREN",
      topic_placeholder: "For example: tools for students before exams",
      btn_ideas: "Get ideas",
      style_label: "STYLE FROM FRONTREN",
      style_placeholder: "The product and who it is for, or leave empty",
      btn_styles: "Show styles",
      style_files_hint: "screenshots you like: Pinterest, Dribbble, anything",
      open_drawer: "Open skills and activity",
      task_label: "TASK FOR",
      dev_label: "Who gets the task",
      dev_backend_title: "backren: data, APIs, logic",
      dev_frontend_title: "frontren: pages, components, style",
      btn_task: "Give task",
      btn_attach: "📎 Attach files",
      btn_projects: "◂ Projects",
      projects_heading: "PROJECTS",
      new_project_label: "New project",
      new_project_placeholder: "For example: hackathon-timer",
      btn_create: "Create",
      projects_empty: "No projects yet. Create the first one above.",
      open_folder_label: "Open a folder from elsewhere",
      open_folder_placeholder: "For example: C:\\Users\\you\\Desktop\\my-app",
      btn_open: "Open",
      files_hint: "or drop them here, or paste a screenshot",
      btn_review: "Call checkren",
      btn_rework: "Send back",
      btn_accept: "Accept",
      btn_stop: "Stop",
      autopilot_label: "AUTOPILOT",
      rounds_label: "Max rounds",
      log_title: "LOG",
      log_empty: "All quiet. Give backren or frontren a task.",
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
    task_placeholder: {
      backend: "For example: an API that keeps notes in SQLite, with tests",
      frontend: "For example: a landing page for the timer, phone first",
    },
    hint_working: (name) => `${name} is working. You can call checkren when the work is ready.`,
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
    verdict_sent: (name) => `Notes sent to ${name}`,
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
    projects_in: (folder) => `Each project is a folder in ${folder}`,
    open_project: "Open",
    project_now: (title) => `now: ${title}`,
    project_last: (title) => `last done: ${title}`,
    project_fresh: "nothing done yet",
    project_done: (n) => `tasks done: ${n}`,
    error_status: (code) => `Error ${code}`,
    no_connection: "Cannot reach the server",
    empty_task: "Write what needs to be done",
    empty_topic: "Write a topic for the ideas",
    ideas_for: (topic) => `Ideas on “${topic}”`,
    recommended: "recommended",
    scope: { small: "small", medium: "medium", large: "large" },
    brief: (name) => `Brief for ${name}`,
    interface: "Interface:",
    hand_off: (name) => `Give to ${name}`,
    hand_other: (name) => `or to ${name}`,
    handed: (name) => `With ${name}`,
    fonts: (heading, body) => `${heading} · ${body}`,
    preview_button: "Start",
    style_more: "Shapes, components, references",
    style_shapes: "Shapes:",
    style_components: "Components:",
    style_fits: "Why it fits:",
    choose_style: "Choose",
    chosen_style: "✓ In DESIGN.md",
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
    remove_file: (name) => `Remove ${name}`,
    file_too_big: (name) => `${name} is larger than 20 MB`,
  },
  ru: {
    names: { backend: "backren", frontend: "frontren", reviewer: "checkren", ideator: "idearen", user: "Ты", office: "Офис" },
    roles: { backend: "Бэкенд-разработчик", frontend: "Фронтенд-разработчик", reviewer: "Ревьюер", ideator: "Генератор идей" },
    // Present tense and impersonal forms, so no status guesses anyone's gender.
    status: {
      idle: "отдыхает", working: "работает", reviewing: "проверяет", approved: "одобрено", rejected: "есть замечания",
      thinking: "думает", ready: "идеи готовы", sleeping: "спит",
    },
    static: {
      connecting: "подключаюсь…",
      cost_title: "Стоимость по оценке Claude Code; с подпиской списываются лимиты, а не деньги",
      limits_label: "Лимиты подписки",
      scene_label: "Пиксельный офис: сзади backren и checkren, спереди frontren и idearen. Нажми на агента, чтобы увидеть его навыки.",
      topic_label: "ТЕМА ДЛЯ IDEAREN",
      topic_placeholder: "Например: инструменты для студентов перед сессией",
      btn_ideas: "Придумать идеи",
      style_label: "СТИЛЬ ОТ FRONTREN",
      style_placeholder: "Что это и для кого, или оставь пустым",
      btn_styles: "Показать стили",
      style_files_hint: "скриншоты, которые нравятся: Pinterest, Dribbble, что угодно",
      open_drawer: "Открыть навыки и действия",
      task_label: "ЗАДАЧА ДЛЯ",
      dev_label: "Кому задача",
      dev_backend_title: "backren: данные, API, логика",
      dev_frontend_title: "frontren: страницы, компоненты, стиль",
      btn_task: "Дать задачу",
      btn_attach: "📎 Прикрепить файлы",
      btn_projects: "◂ Проекты",
      projects_heading: "ПРОЕКТЫ",
      new_project_label: "Новый проект",
      new_project_placeholder: "Например: таймер-для-хакатона",
      btn_create: "Создать",
      projects_empty: "Проектов пока нет. Создай первый выше.",
      open_folder_label: "Открыть папку из другого места",
      open_folder_placeholder: "Например: C:\\Users\\you\\Desktop\\my-app",
      btn_open: "Открыть",
      files_hint: "или перетащи их сюда, или вставь скриншот",
      btn_review: "Позвать checkren",
      btn_rework: "На доработку",
      btn_accept: "Принять",
      btn_stop: "Стоп",
      autopilot_label: "АВТОПИЛОТ",
      rounds_label: "Раундов, не больше",
      log_title: "ЖУРНАЛ",
      log_empty: "Пока тихо. Дай задачу backren или frontren.",
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
    task_placeholder: {
      backend: "Например: API для заметок с хранением в SQLite и тестами",
      frontend: "Например: лендинг для таймера, сначала под телефон",
    },
    hint_working: (name) => `${name} работает. checkren можно позвать, когда работа будет готова.`,
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
    verdict_sent: (name) => `Замечания отправлены ${name}`,
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
    projects_in: (folder) => `Каждый проект — папка в ${folder}`,
    open_project: "Открыть",
    project_now: (title) => `сейчас: ${title}`,
    project_last: (title) => `последнее: ${title}`,
    project_fresh: "пока ничего не сделано",
    project_done: (n) => `принято задач: ${n}`,
    error_status: (code) => `Ошибка ${code}`,
    no_connection: "Нет связи с сервером",
    empty_task: "Напиши, что нужно сделать",
    empty_topic: "Напиши тему для идей",
    ideas_for: (topic) => `Идеи по теме «${topic}»`,
    recommended: "рекомендую",
    scope: { small: "небольшая", medium: "средняя", large: "большая" },
    brief: (name) => `ТЗ для ${name}`,
    interface: "Интерфейс:",
    hand_off: (name) => `Передать ${name}`,
    hand_other: (name) => `или ${name}`,
    handed: (name) => `У ${name}`,
    fonts: (heading, body) => `${heading} · ${body}`,
    preview_button: "Начать",
    style_more: "Формы, компоненты, референсы",
    style_shapes: "Формы:",
    style_components: "Компоненты:",
    style_fits: "Почему подходит:",
    choose_style: "Выбрать",
    chosen_style: "✓ В DESIGN.md",
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
    remove_file: (name) => `Убрать ${name}`,
    file_too_big: (name) => `${name} больше 20 МБ`,
  },
};

const LOG_KEEP = 500;
const AGENTS = ["backend", "frontend", "reviewer", "ideator"];
const DEVELOPERS = ["backend", "frontend"];
const DEVELOPER_KEY = "rens-office-developer";

let state = null;
let lang = "en";
const log = []; // every entry the server sent, for the drawer's per-agent activity
let drawerAgent = null;
let drawerOpener = null;
let taskDeveloper = "backend"; // who the next task goes to
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
  $("task-input").placeholder = S().task_placeholder[taskDeveloper];
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
  for (const agent of AGENTS) {
    if (state.agents[agent]) $(`status-${agent}`).textContent = statusText(agent, state.agents[agent].status);
  }
  if (drawerAgent) renderDrawer();
}

// A bubble shows the start of what the agent says; the log and its drawer have all of it.
function setBubble(agent, text) {
  const bubble = $(`bubble-${agent}`);
  const line = bubble.firstElementChild;
  if (line.textContent !== text) {
    line.textContent = text;
    bubble.classList.remove("pop");
    void bubble.offsetWidth; // restart the animation
    bubble.classList.add("pop");
  }
}

function render(s) {
  state = s;
  if (s.lang && s.lang !== lang) applyLanguage(s.lang);
  renderLimits(s.limits, s.limits_checking);
  // Without an open project the page is the project list.
  const listing = !s.project;
  $("projects-view").hidden = !listing;
  $("office-view").hidden = listing;
  $("btn-projects").hidden = listing;
  // The list has no office to check the limits with; it shows them once a project has.
  $("limits").hidden = listing && !s.limits?.length;
  if (listing) {
    renderProjects(s);
    return;
  }
  const t = S();
  $("workspace").textContent = s.project.path;
  $("workspace").title = s.project.path;
  $("cost").textContent = formatCost(s.cost_usd);

  for (const agent of AGENTS) {
    const a = s.agents[agent];
    if (!a) continue;
    $(`desk-${agent}`).dataset.status = a.status;
    setBubble(agent, a.bubble.replace(/`/g, ""));
    $(`status-${agent}`).textContent = statusText(agent, a.status);
  }

  const workingDev = DEVELOPERS.find((dev) => s.agents[dev]?.status === "working");
  const working = Boolean(workingDev);
  // A developer looking for a style takes no task until it is done.
  const looking = (dev) => s.agents[dev]?.status === "thinking";
  const reviewing = s.agents.reviewer.status === "reviewing";
  const busy = working || reviewing;
  const started = s.task !== null;
  const fresh = Boolean(s.verdict && !s.verdict.sent);
  const needsRework = fresh && !s.verdict.approved;
  const hasIssues = fresh && s.verdict.issues.length > 0;

  $("btn-task").disabled = busy || looking(taskDeveloper);
  $("btn-review").disabled = busy || !started;
  $("btn-rework").disabled = busy || looking(ownerOf(s)) || !(needsRework || hasIssues);
  $("btn-accept").disabled = busy || !started;
  $("btn-stop").disabled = !working;

  let hint = "";
  if (working) hint = t.hint_working(t.names[workingDev]);
  else if (reviewing) hint = t.hint_reviewing;
  else if (s.verdict?.sent) hint = t.hint_sent;
  else if (needsRework) hint = t.hint_rework;
  else if (s.verdict?.approved && hasIssues) hint = t.hint_approved_notes;
  else if (s.verdict?.approved) hint = t.hint_approved;
  else if (started) hint = t.hint_started;
  $("hint").textContent = hint;

  renderAutopilot(s.autopilot);
  renderIdeas(s, busy);
  renderStyles(s, busy);
  renderVerdict(s.verdict, ownerOf(s));
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

function renderProjects(s) {
  const t = S();
  $("workspace").textContent = s.projects_dir;
  $("workspace").title = s.projects_dir;
  $("projects-dir").textContent = t.projects_in(s.projects_dir);
  $("projects-empty").hidden = s.projects.length > 0;
  $("project-list").replaceChildren(...s.projects.map((project) => {
    const li = document.createElement("li");
    li.className = "project-item";
    const about = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = project.name;
    const info = document.createElement("span");
    info.className = "project-info";
    const where = project.task ? t.project_now(project.task)
      : project.last_done ? t.project_last(project.last_done) : t.project_fresh;
    const when = new Date(project.updated * 1000).toLocaleString(lang, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
    info.textContent = [where, t.project_done(project.done), when].join(" · ");
    about.append(name, info);
    const open = document.createElement("button");
    open.type = "button";
    open.className = "btn primary";
    open.textContent = t.open_project;
    open.addEventListener("click", () => projectAction("/api/projects/open", { path: project.path }));
    li.append(about, open);
    return li;
  }));
}

// Opening, creating or leaving a project changes the whole page, so it loads again: once, though
// both the answer and the server's event about the switch ask for it.
let reloading = false;

function reloadPage() {
  if (reloading) return;
  reloading = true;
  location.reload();
}

async function projectAction(path, body = {}) {
  if (await post(path, body)) reloadPage();
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
    button.disabled = busy || idea.handed || s.agents[button.dataset.developer]?.status === "thinking";
  });
}

// ---------- frontren's styles ----------

let stylesKey = "";

function renderStyles(s, busy) {
  const t = S();
  const frontren = s.agents.frontend?.status;
  $("btn-styles").disabled = frontren === "thinking" || frontren === "working";
  $("btn-styles-stop").disabled = frontren !== "thinking";
  const list = $("style-cards");
  // Rebuild only when the styles change, so open details stay open when one is chosen.
  const key = JSON.stringify([lang, s.styles]);
  if (key !== stylesKey) {
    const names = (styles) => (styles?.directions || []).map((d) => d.name).join("\n");
    const same = stylesKey && names(JSON.parse(stylesKey)[1]) === names(s.styles);
    const open = same ? [...list.querySelectorAll("details")].map((d) => d.open) : [];
    stylesKey = key;
    const directions = s.styles?.directions || [];
    loadFonts(directions);
    list.replaceChildren(...directions.map((direction, index) => styleCard(direction, index, s.styles, t)));
    list.querySelectorAll("details").forEach((d, i) => (d.open = Boolean(open[i])));
  }
  // Writing DESIGN.md waits while a developer works or checkren reviews.
  list.querySelectorAll(".style-choose").forEach((button) => (button.disabled = busy));
}

// The colors a preview needs, found by role: frontren names them background, text and accent.
function pick(palette, word, fallback) {
  const found = palette.find((swatch) => swatch.role.toLowerCase().includes(word) && !/muted/i.test(swatch.role));
  return (found || palette[fallback] || palette[0]).hex;
}

function styleCard(direction, index, styles, t) {
  const li = document.createElement("li");
  li.className = "style";
  li.dataset.chosen = String(styles.chosen === index);

  const head = document.createElement("div");
  head.className = "idea-head";
  const name = document.createElement("strong");
  name.textContent = direction.name;
  const mood = document.createElement("span");
  mood.className = "mood";
  mood.textContent = direction.mood;
  head.append(name, mood);
  if (styles.recommended === index) {
    const star = document.createElement("span");
    star.className = "star";
    star.textContent = `★ ${t.recommended}`;
    head.append(star);
  }

  const swatches = document.createElement("div");
  swatches.className = "swatches";
  swatches.setAttribute("role", "img");
  swatches.setAttribute("aria-label", direction.palette.map((swatch) => `${swatch.role} ${swatch.hex}`).join(", "));
  swatches.append(...direction.palette.map((swatch) => {
    const chip = document.createElement("span");
    chip.className = "swatch";
    chip.style.background = swatch.hex; // checked as #rrggbb by the server
    chip.title = `${swatch.role}: ${swatch.hex}`;
    return chip;
  }));

  // A small piece of interface in this style: its colors and its two fonts.
  const preview = document.createElement("div");
  preview.className = "style-preview";
  const background = pick(direction.palette, "background", 0);
  preview.style.background = background;
  preview.style.color = pick(direction.palette, "text", 1);
  preview.style.fontFamily = fontStack(direction.body_font);
  const title = document.createElement("strong");
  title.textContent = direction.name;
  title.style.fontFamily = fontStack(direction.heading_font);
  const fonts = document.createElement("span");
  fonts.textContent = t.fonts(direction.heading_font, direction.body_font);
  const button = document.createElement("span");
  button.className = "preview-button";
  button.textContent = t.preview_button;
  button.style.background = pick(direction.palette, "accent", 2);
  button.style.color = background;
  preview.append(title, fonts, button);

  const summary = document.createElement("p");
  richText(summary, direction.summary);

  const details = document.createElement("details");
  const more = document.createElement("summary");
  more.textContent = t.style_more;
  const body = document.createElement("div");
  body.className = "brief";
  for (const [label, text] of [[t.style_shapes, direction.shapes], [t.style_components, direction.components],
    [t.style_fits, direction.fits]]) {
    const p = document.createElement("p");
    const strong = document.createElement("strong");
    strong.textContent = label;
    const span = document.createElement("span");
    richText(span, text);
    p.append(strong, " ", span);
    body.append(p);
  }
  if (direction.references.length) {
    const refs = document.createElement("ul");
    refs.className = "references";
    refs.append(...direction.references.map((ref) => {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.textContent = ref.title;
      if (/^https?:\/\//i.test(ref.url)) {
        link.href = ref.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
      }
      item.append(link, ` — ${ref.take}`);
      return item;
    }));
    body.append(refs);
  }
  details.append(more, body);

  const choose = document.createElement("button");
  choose.type = "button";
  choose.className = "btn style-choose";
  choose.dataset.index = String(index);
  choose.textContent = styles.chosen === index ? t.chosen_style : t.choose_style;
  choose.setAttribute("aria-label", `${choose.textContent}: ${direction.name}`);

  li.append(head, swatches, preview, summary, details, choose);
  return li;
}

// The fonts a direction names, from Google Fonts like the page's own; each is fetched once.
const loadedFonts = new Set();

function loadFonts(directions) {
  for (const direction of directions) {
    for (const family of [direction.heading_font, direction.body_font]) {
      const name = String(family || "").trim();
      if (!name || loadedFonts.has(name) || loadedFonts.size >= 24) continue;
      loadedFonts.add(name);
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(name).replace(/%20/g, "+")}&display=swap`;
      document.head.append(link);
    }
  }
}

// A font name as a CSS string, so no name can break out of the font-family value.
function fontStack(name) {
  return `${JSON.stringify(String(name))}, system-ui, sans-serif`;
}

// The developer who has the current task; its review notes go back to it.
function ownerOf(s) {
  return DEVELOPERS.includes(s?.owner) ? s.owner : "backend";
}

function handoffButton(index, title, developer, label, className) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `btn idea-handoff ${className}`;
  button.dataset.index = String(index);
  button.dataset.developer = developer;
  button.textContent = label;
  // Every card has the same buttons, so a screen reader also hears which idea each one gives away.
  button.setAttribute("aria-label", `${label}: ${title}`);
  return button;
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
  // idearen's pick of who builds it; the other developer can still take it.
  const developer = DEVELOPERS.includes(idea.developer) ? idea.developer : "backend";
  const other = developer === "backend" ? "frontend" : "backend";
  const who = document.createElement("span");
  who.className = "dev-tag";
  who.dataset.developer = developer;
  who.textContent = `→ ${t.names[developer]}`;
  head.append(title, scope, who);
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
  summary.textContent = t.brief(t.names[developer]);
  const brief = document.createElement("div");
  brief.className = "brief";
  richText(brief, idea.task);
  details.append(summary, brief);
  if (idea.ui) {
    // what idearen wants the interface to be and feel like; frontren picks the style
    const ui = document.createElement("div");
    ui.className = "brief ui-brief";
    const label = document.createElement("strong");
    label.textContent = t.interface;
    const text = document.createElement("span");
    richText(text, idea.ui);
    ui.append(label, " ", text);
    details.append(ui);
  }

  const actions = document.createElement("div");
  actions.className = "idea-actions";
  if (idea.handed) {
    actions.append(handoffButton(index, idea.title, developer, `✓ ${t.handed(t.names[developer])}`, "main"));
  } else {
    actions.append(
      handoffButton(index, idea.title, developer, t.hand_off(t.names[developer]), "main"),
      handoffButton(index, idea.title, other, t.hand_other(t.names[other]), "ghost other"),
    );
  }

  li.append(head, pitch, why, details, actions);
  return li;
}

let verdictKey = "";

function renderVerdict(v, owner) {
  // Rebuild only when the verdict changes, so text someone is selecting stays selected.
  const key = JSON.stringify([lang, v, owner]);
  if (key === verdictKey) return;
  verdictKey = key;
  const t = S();
  const box = $("verdict");
  box.hidden = !v;
  if (!v) return;
  box.dataset.approved = String(v.approved);
  box.dataset.sent = String(Boolean(v.sent));
  $("verdict-stamp").textContent = v.approved ? "✓" : "✗";
  $("verdict-title").textContent = v.sent ? t.verdict_sent(t.names[owner]) : v.approved ? t.verdict_approved : t.verdict_rejected;
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
    else if (event.type === "reload") reloadPage();
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
  if (await post("/api/task", { text: input.value, developer: taskDeveloper, files: attached.task })) {
    input.value = "";
    clearFiles("task");
  }
});
$("task-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) $("task-form").requestSubmit();
});
$("btn-review").addEventListener("click", () => post("/api/review"));
$("btn-rework").addEventListener("click", () => post("/api/rework"));
$("btn-accept").addEventListener("click", () => post("/api/accept"));
$("btn-stop").addEventListener("click", () => {
  const working = DEVELOPERS.find((dev) => state?.agents[dev]?.status === "working");
  if (working) post("/api/stop", { agent: working });
});
$("limits").addEventListener("click", () => post("/api/limits"));

$("ideas-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("topic-input");
  if (!input.value.trim()) {
    toast(S().empty_topic);
    input.focus();
    return;
  }
  if (await post("/api/ideas", { topic: input.value, files: attached.topic })) clearFiles("topic");
});
$("btn-ideas-stop").addEventListener("click", () => post("/api/stop", { agent: "ideator" }));
$("idea-cards").addEventListener("click", (e) => {
  const button = e.target.closest(".idea-handoff");
  if (button && !button.disabled) {
    post("/api/handoff", { index: Number(button.dataset.index), developer: button.dataset.developer });
  }
});

$("style-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  // An empty brief is fine: frontren then works it out from the project and its task.
  if (await post("/api/styles", { brief: $("style-input").value, files: attached.style })) clearFiles("style");
});
$("btn-styles-stop").addEventListener("click", () => post("/api/stop", { agent: "frontend" }));
$("style-cards").addEventListener("click", (e) => {
  const button = e.target.closest(".style-choose");
  if (button && !button.disabled) post("/api/style", { index: Number(button.dataset.index) });
});

// ---------- who gets the task ----------

function setTaskDeveloper(developer) {
  taskDeveloper = DEVELOPERS.includes(developer) ? developer : "backend";
  document.querySelectorAll(".dev-switch button").forEach((b) => {
    b.setAttribute("aria-pressed", String(b.dataset.developer === taskDeveloper));
  });
  $("task-form").dataset.developer = taskDeveloper;
  $("task-input").placeholder = S().task_placeholder[taskDeveloper];
  if (state?.agents) render(state); // the task button waits for a developer looking for a style
  try {
    localStorage.setItem(DEVELOPER_KEY, taskDeveloper);
  } catch {
    // storage can be unavailable (private mode); the choice still holds for this visit
  }
}

document.querySelectorAll(".dev-switch button").forEach((button) => {
  button.addEventListener("click", () => setTaskDeveloper(button.dataset.developer));
});

// ---------- files for the agents ----------

// Files attached to the next task or topic. Each is uploaded at once; the task names them.
const attached = { task: [], topic: [], style: [] };
const MAX_FILE_BYTES = 20 * 1024 * 1024;

function renderFiles(kind) {
  $(`${kind}-files`).replaceChildren(...attached[kind].map((name, index) => {
    const li = document.createElement("li");
    li.className = "file-chip";
    const label = document.createElement("span");
    label.textContent = name;
    label.title = name;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "✕";
    remove.setAttribute("aria-label", S().remove_file(name));
    remove.addEventListener("click", () => {
      attached[kind].splice(index, 1);
      renderFiles(kind);
    });
    li.append(label, remove);
    return li;
  }));
}

function clearFiles(kind) {
  attached[kind] = [];
  renderFiles(kind);
}

async function attachFiles(kind, files) {
  for (const file of files) {
    if (file.size > MAX_FILE_BYTES) {
      toast(S().file_too_big(file.name));
      continue;
    }
    const name = await uploadFile(file);
    if (name) {
      attached[kind].push(name);
      renderFiles(kind);
    }
  }
}

// JSON rather than a form upload: like every other request, a cross-site page can't send it.
async function uploadFile(file) {
  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: file.name, data: await readBase64(file) }),
    });
    const data = await res.json();
    if (res.ok) return data.name;
    toast(data.error || S().error_status(res.status));
  } catch {
    toast(S().no_connection);
  }
  return null;
}

function readBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1] || "");
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

const FILE_FORMS = [["task", "task-form", "task-input"], ["topic", "ideas-form", "topic-input"], ["style", "style-form", "style-input"]];
for (const [kind, formId, inputId] of FILE_FORMS) {
  const picker = $(`${kind}-file-input`);
  $(`${kind}-attach`).addEventListener("click", () => picker.click());
  picker.addEventListener("change", () => {
    attachFiles(kind, [...picker.files]);
    picker.value = "";
  });

  const form = $(formId);
  form.addEventListener("dragover", (e) => {
    if (!e.dataTransfer?.types.includes("Files")) return;
    e.preventDefault();
    form.classList.add("dropping");
  });
  form.addEventListener("dragleave", (e) => {
    if (!form.contains(e.relatedTarget)) form.classList.remove("dropping");
  });
  form.addEventListener("drop", (e) => {
    form.classList.remove("dropping");
    if (!e.dataTransfer?.files.length) return;
    e.preventDefault();
    attachFiles(kind, [...e.dataTransfer.files]);
  });

  // A screenshot pasted into the text box comes as a file.
  $(inputId).addEventListener("paste", (e) => {
    const files = [...(e.clipboardData?.files || [])];
    if (!files.length) return;
    e.preventDefault();
    attachFiles(kind, files);
  });
}

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
$("btn-projects").addEventListener("click", () => projectAction("/api/projects/close"));
$("new-project-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = $("new-project-name");
  if (input.value.trim()) projectAction("/api/projects/new", { name: input.value });
});
$("open-folder-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = $("open-folder-path");
  if (input.value.trim()) projectAction("/api/projects/open", { path: input.value.trim() });
});
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

let savedDeveloper = "backend";
try {
  savedDeveloper = localStorage.getItem(DEVELOPER_KEY) || "backend";
} catch {
  // keep backren
}

applyLanguage(lang);
setTaskDeveloper(savedDeveloper);
setTimeMode(savedTime);
connect();
