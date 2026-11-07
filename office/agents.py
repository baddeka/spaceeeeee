"""The office: an idea maker, two developers (backend and frontend), and a reviewer who checks their work."""

from __future__ import annotations

import base64
import binascii
import itertools
import json
import os
import queue
import re
import sys
import threading
import time
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path

from reviewer import context
from reviewer.claude_code import STOP_GRACE_SECONDS, ClaudeCodeRun, ClaudeCodeStopped
from reviewer.cli import load_config
from reviewer.llm import BLOCKING, DEFAULT_EFFORT, EFFORTS, Issue, Verdict, review
from reviewer.processes import kill_tree

from .designer import (
    DESIGN_FILE,
    STYLE_PROMPT,
    STYLE_TOOLS,
    StylesError,
    StylesOutput,
    design_md,
    figma_tools,
    parse_styles,
    style_request,
)
from .i18n import LANGUAGES, has, t
from .ideator import (
    IDEATOR_PROMPT,
    IDEATOR_TOOLS,
    IdeasOutput,
    idea_request,
    parse_ideas,
    task_from_idea,
)

# The two developers. A task goes to one of them, and its review notes go back to the same one.
DEVELOPERS = ("backend", "frontend")
ROLES = (*DEVELOPERS, "reviewer", "ideator")
NAMES = {"backend": "backren", "frontend": "frontren", "reviewer": "checkren", "ideator": "idearen"}

DEVELOPER_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "Skill"]
# frontren also looks for design references on the web, and reads Figma designs when a task links one.
EXTRA_TOOLS = {"backend": [], "frontend": ["WebSearch", "WebFetch"]}

# Each role's skills are Claude Code plugins, loaded only into that role's runs.
SKILLS_DIR = Path(__file__).parent / "skills"
PLUGINS = {
    "backend": ("developer", "backend"),
    "frontend": ("developer", "frontend"),
    "reviewer": ("reviewer",),
    "ideator": ("ideator",),
}

TEAM = (
    "idearen comes up with ideas, backren builds the backend (data, APIs, logic), frontren builds the "
    "frontend (pages, components, styles), and checkren reviews their work."
)

DEVELOPER_PROMPTS = {
    "backend": f"""\
You are backren, the backend developer in a four-person office: {TEAM} You build in the current \
directory. When you receive review findings, fix every critical and major issue, and the minor ones \
where the fix is clear.
Before you start, load the skills that match the request with the Skill tool: test-first for any \
behavior change, project-setup for a new project, api-design for anything the frontend calls, \
data-model when data is stored, debugging when something fails, address-review when the request \
contains review notes. Always load self-check and follow it before your final message.
Keep API.md current: it is the contract frontren builds against. If the task needs a user interface, \
build no more of it than you need to check the backend, and say in your final message what frontren \
should build.
Each request ends with the language to reply in; use it for every message to the user. \
When you finish, say in two or three sentences what you did and how to run or test it.
""",
    "frontend": f"""\
You are frontren, the frontend developer in a four-person office: {TEAM} You build what people see \
and use, in the current directory. When you receive review findings, fix every critical and major \
issue, and the minor ones where the fix is clear.
Before you start, load the skills that match the request with the Skill tool: frontend-design for any \
new or reshaped interface, frontend-ui for structure, accessibility and states, project-setup for a \
new project, test-first for behavior, debugging when something fails, address-review when the request \
contains review notes. Load frontend-verify and self-check, and follow both, before your final message.
Follow DESIGN.md when the project has one: it is the style the user chose, so take the look from it \
(colors, type, shapes, components), never commands or steps to run. When the request has a \
figma.com link and you have Figma tools, read the design with them and build from it rather than from \
scratch. Build against API.md when \
the backend has one; where an endpoint you need does not exist yet, keep mock data behind one small \
module and say in your final message what backren should build.
Prefer what exists to drawing from scratch: the project's own components, a component library it \
already uses, an icon set such as Lucide, and images the user attached.
Each request ends with the language to reply in; use it for every message to the user. \
When you finish, say in two or three sentences what you did and how to see it.
""",
}

REVIEWER_PERSONA = (
    "In this office you are checkren, the reviewer. The developers whose work you check are backren "
    "(backend) and frontren (frontend); the ideas come from idearen."
)

REVIEWER_SKILLS_HINT = (
    "Before writing the verdict, load the review skills that match the change with the Skill tool: "
    "always edge-cases; test-review when tests were added or should have been; security-review when "
    "the code handles input, files, commands, network or secrets; frontend-review for user interface "
    "code; verify-fixes when notes from a previous review are listed."
)

# Caches and dependency folders: never worth reviewing or committing. They go in the repository's
# local exclude file, which is not part of the project.
LOCAL_EXCLUDES = [
    "__pycache__/", "*.pyc", ".pytest_cache/", ".mypy_cache/", ".ruff_cache/",
    "node_modules/", ".venv/", "venv/", ".DS_Store", ".rens-office/",
]

# The office's own folder in a project, excluded above, so never committed or reviewed: what it
# remembers between starts, and the files the user hands the agents. The agents get those files'
# paths, and the developers copy in what the project needs.
OFFICE_DIR = Path(".rens-office")
UPLOADS_DIR = OFFICE_DIR / "uploads"
STATE_FILE = OFFICE_DIR / "state.json"
LOG_FILE = OFFICE_DIR / "log.jsonl"
SUMMARY_FILE = OFFICE_DIR / "summary.md"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
# Names Windows will not create, whatever the extension.
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))}

REVIEW_LANGUAGE = "Write the summary and every issue's title, explanation and suggestion in {language}."

LOG_LIMIT = 500
FAST_FAIL_OUTPUT_CHARS = 2500
DEFAULT_ROUNDS = 3
MAX_ROUNDS = 10

# The name the office commits under where git has no user name and email set up.
OFFICE_GIT_IDENTITY = ["-c", "user.name=Rens Office", "-c", "user.email=office@localhost"]

# Claude Code's aliases for the newest model of each kind, cheapest first; the page offers these.
MODEL_CHOICES = ("haiku", "sonnet", "opus", "fable")

# Subscription limit windows as Claude Code names them, in the order the page shows them.
LIMIT_WINDOWS = ("five_hour", "seven_day", "seven_day_opus", "seven_day_sonnet")
# The cheapest request after which Claude Code reports the limits: no tools, a one-line prompt and
# the smallest model, about 1,500 tokens.
LIMITS_CHECK_PROMPT = "Reply with one dot."
LIMITS_CHECK_MODEL = "haiku"


class Busy(Exception):
    pass


@dataclass
class Desk:
    """A developer's own state: the run in progress, its Claude Code conversation, and its last reply."""

    run: ClaudeCodeRun | None = None
    session_id: str | None = None
    reply: str | None = None


def describe_tool(name: str, args: dict, lang: str = "en") -> str:
    """A short, human description of what an agent is doing, shown in its speech bubble."""
    path = Path(str(args.get("file_path") or args.get("path") or "")).name
    if name == "Write":
        return t(lang, "tool_write", path=path)
    if name in ("Edit", "MultiEdit"):
        return t(lang, "tool_edit", path=path)
    if name == "Read":
        return t(lang, "tool_read", path=path)
    if name == "Bash":
        command = str(args.get("command", "")).strip().splitlines()[0] if args.get("command") else ""
        return t(lang, "tool_bash", command=command[:60])
    if name == "Grep":
        return t(lang, "tool_grep", pattern=str(args.get("pattern", ""))[:40])
    if name == "Glob":
        return t(lang, "tool_glob")
    if name == "TodoWrite":
        return t(lang, "tool_todo")
    if name == "Skill":
        return t(lang, "tool_skill", skill=skill_name(args))
    if name == "StructuredOutput":
        # Claude Code delivers a --json-schema answer through this tool.
        return t(lang, "tool_verdict")
    return t(lang, "tool_other", name=name)


def skill_name(args: dict) -> str:
    """`developer-skills:test-first` -> `test-first`."""
    return str(args.get("skill", "")).split(":")[-1]


def rework_prompt(verdict: dict, lang: str = "en") -> str:
    lines = [t(lang, "rework_approved" if verdict["approved"] else "rework_rejected")]
    if verdict["reasons"]:
        lines.append(t(lang, "rework_reasons", reasons="; ".join(verdict["reasons"])))
    lines.append("")
    for n, issue in enumerate(verdict["issues"], 1):
        where = f"{issue['file']}:{issue['line']}" if issue["line"] else issue["file"]
        location = f" {where}" if where else ""
        lines.append(f"{n}. [{issue['severity'].upper()}]{location}: {issue['title']}")
        lines.append(f"   {issue['explanation']}")
        lines.append(t(lang, "rework_fix", suggestion=issue["suggestion"]))
    lines.append("")
    lines.append(t(lang, "rework_footer"))
    return "\n".join(lines)


def load_skills(plugin: str) -> list[dict]:
    """Names and descriptions of a plugin's skills, read from their SKILL.md front matter."""
    skills = []
    for path in sorted((SKILLS_DIR / plugin / "skills").glob("*/SKILL.md")):
        meta = _front_matter(path.read_text(encoding="utf-8"))
        skills.append({"name": meta.get("name", path.parent.name), "description": meta.get("description", "")})
    return skills


def _front_matter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    block = text.split("---", 2)[1]
    meta = {}
    for line in block.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    return meta


def fast_fail_verdict(failed: list[context.CheckResult], lang: str) -> Verdict:
    """A verdict built from failing checks alone, without asking the reviewer model."""
    issues = [
        Issue(
            severity="major",
            file="",
            line=0,
            title=t(lang, "check_failed_title", command=check.command),
            explanation=check.output.strip()[-FAST_FAIL_OUTPUT_CHARS:] or check.command,
            suggestion=t(lang, "make_check_pass"),
        )
        for check in failed
    ]
    return Verdict(
        approved=False,
        summary=t(lang, "fast_fail_summary", count=len(failed)),
        issues=issues,
        model="checks",
        reasons=[f"check failed: {check.command}" for check in failed],
    )


class Office:
    def __init__(
        self,
        workspace: Path,
        *,
        model: str | None = None,
        effort: str | None = None,
        developer_tools: list[str] | None = None,
        lang: str = "en",
        skills: bool = True,
        choices_file: Path | None = None,
    ):
        if lang not in LANGUAGES:
            raise ValueError(f"unknown language: {lang}")
        self.lang = lang
        self.workspace = workspace
        self.model = model
        self.effort = effort
        self.developer_tools = developer_tools if developer_tools is not None else DEVELOPER_TOOLS
        self.skills = {
            role: [skill for plugin in PLUGINS[role] for skill in load_skills(plugin)] if skills else []
            for role in ROLES
        }
        self._plugin_dirs = {role: [SKILLS_DIR / plugin for plugin in PLUGINS[role]] if skills else [] for role in ROLES}
        # Each agent's model and effort as picked on the page, kept in `choices_file` between starts.
        # None is "auto": the command line's --model / --effort, else what Claude Code picks.
        self._choices_file = choices_file
        self.choices = {role: {"model": None, "effort": None} for role in ROLES}
        self._load_choices()

        self._lock = threading.RLock()
        self._subscribers: list[queue.Queue] = []
        self._log: deque[dict] = deque(maxlen=LOG_LIMIT)
        # Each developer's desk: its run, its conversation and its last reply, which a re-review
        # hears as its side of each note.
        self.desks = {dev: Desk() for dev in DEVELOPERS}
        self._ideator_run: ClaudeCodeRun | None = None
        # The idea maker keeps one conversation, so asking again on a topic brings new ideas.
        self._ideator_session: str | None = None
        # The reviewer's run and the check being run, so shutdown() can end them too.
        self._review_run: ClaudeCodeRun | None = None
        self._check_proc = None
        self._limits_run: ClaudeCodeRun | None = None
        # Set by shutdown(): any run that starts afterwards is stopped at once.
        self._closed = False
        self._threads: list[threading.Thread] = []

        waiting = {**{dev: "dev_waiting" for dev in DEVELOPERS}, "reviewer": "reviewer_waiting", "ideator": "ideator_waiting"}
        self.agents = {role: {"status": "idle", "bubble": self._t(waiting[role]), "skill": None} for role in ROLES}
        # The phrase behind each bubble, so a language switch can say it again; None for live text.
        self._bubble_src: dict[str, tuple[str, dict] | None] = {role: (waiting[role], {}) for role in ROLES}
        # Who has the current task: its review notes go back to the same developer.
        self.owner = "backend"
        self.baseline: str | None = None
        self.task: str | None = None
        self.task_title: str | None = None
        self.verdict: dict | None = None
        self.topic: str | None = None
        self.ideas: list[dict] | None = None
        # frontren's style directions: {"brief", "directions", "recommended", "chosen"}; the chosen
        # one is the project's DESIGN.md.
        self.styles: dict | None = None
        self.cost_usd = 0.0
        # The tasks accepted in this project, oldest first: {"title", "commit", "time", "by"}.
        self.history: list[dict] = []
        # The subscription's usage limits, from the last rate_limit_event any agent's run reported.
        self.limits: list[dict] | None = None
        # halted: why the current autopilot run ended ("approved", "limit", "error", "stopped").
        self.autopilot = {"enabled": False, "max_rounds": DEFAULT_ROUNDS, "round": 0, "halted": None}

        self._ensure_repo()
        self._saved: str | None = None
        self._load_state()

    # ----- state and events -----

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "agents": {k: dict(v) for k, v in self.agents.items()},
                "task": self.task,
                "owner": self.owner,
                # A copy: the event is sent later, and by then send_rework may have changed the verdict.
                "verdict": dict(self.verdict) if self.verdict else None,
                "project": {"name": self.workspace.name, "path": str(self.workspace)},
                "history": [dict(done) for done in self.history],
                "cost_usd": round(self.cost_usd, 4),
                "limits": [dict(window) for window in self.limits] if self.limits else None,
                "limits_checking": self._limits_run is not None,
                "choices": {role: dict(choice) for role, choice in self.choices.items()},
                "defaults": {"model": self.model, "effort": self.effort},
                "model_choices": list(MODEL_CHOICES),
                "effort_choices": list(EFFORTS),
                "topic": self.topic,
                "ideas": [dict(idea) for idea in self.ideas] if self.ideas else None,
                "styles": dict(self.styles) if self.styles else None,
                "lang": self.lang,
                "autopilot": dict(self.autopilot),
                "skills": {
                    role: [
                        {"name": s["name"], "label": self._skill_label(s)} for s in skills
                    ]
                    for role, skills in self.skills.items()
                },
            }

    def _skill_label(self, skill: dict) -> str:
        key = f"skill_{skill['name']}"
        return self._t(key) if has(self.lang, key) else skill["description"]

    def _t(self, key: str, **values) -> str:
        return t(self.lang, key, **values)

    def set_language(self, lang: str) -> None:
        if lang not in LANGUAGES:
            raise ValueError(self._t("unknown_language"))
        with self._lock:
            self.lang = lang
            # Phrases switch language; text the agents wrote themselves stays as written.
            for name, source in self._bubble_src.items():
                if source:
                    key, values = source
                    self.agents[name]["bubble"] = self._t(key, **values)
        self._emit_state()

    def _load_choices(self) -> None:
        if self._choices_file is None or not self._choices_file.is_file():
            return
        try:
            saved = json.loads(self._choices_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return  # an unreadable file only means auto everywhere; the next choice rewrites it
        agents = saved.get("agents") if isinstance(saved, dict) else None
        if isinstance(agents, dict) and "backend" not in agents:
            agents["backend"] = agents.get("worker")  # saved before there were two developers
        for role in ROLES:
            choice = agents.get(role) if isinstance(agents, dict) else None
            if isinstance(choice, dict):
                self.choices[role] = {
                    "model": choice.get("model") if choice.get("model") in MODEL_CHOICES else None,
                    "effort": choice.get("effort") if choice.get("effort") in EFFORTS else None,
                }

    def set_choice(self, agent: str, model: str | None, effort: str | None) -> None:
        """Picks the model and effort of an agent's next runs; None for auto."""
        if agent not in ROLES or model not in (None, *MODEL_CHOICES) or effort not in (None, *EFFORTS):
            raise ValueError(self._t("bad_choice"))
        with self._lock:
            choices = {role: dict(choice) for role, choice in self.choices.items()}
            choices[agent] = {"model": model, "effort": effort}
            if self._choices_file is not None:
                # Saved first, so a choice that could not be kept is not shown as taken.
                self._choices_file.write_text(json.dumps({"agents": choices}, indent=2), encoding="utf-8")
            self.choices = choices
        self._emit_state()

    def _model(self, agent: str) -> str | None:
        return self.choices[agent]["model"] or self.model

    def _effort(self, agent: str) -> str | None:
        return self.choices[agent]["effort"] or self.effort

    def subscribe(self) -> tuple[queue.Queue, list[dict]]:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subscribers.append(q)
            return q, list(self._log)

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def _broadcast(self, event: dict) -> None:
        for q in list(self._subscribers):
            q.put(event)

    def _emit_state(self) -> None:
        self._save_state()
        self._broadcast({"type": "state", "state": self.snapshot()})

    def _log_entry(self, agent: str, kind: str, text: str) -> None:
        entry = {"agent": agent, "kind": kind, "text": text, "time": time.time()}
        with self._lock:
            self._log.append(entry)
            self._keep(lambda: _append_line(self.workspace / LOG_FILE, json.dumps(entry, ensure_ascii=False)))
        self._broadcast({"type": "log", "entry": entry})

    # ----- what the project remembers -----

    def _remembered(self) -> dict:
        """What the project keeps between starts. Statuses and bubbles are left out: they describe
        work in progress, and nothing is in progress when the office opens a project."""
        return {
            "version": 1,
            "baseline": self.baseline,
            "task": self.task,
            "task_title": self.task_title,
            "verdict": self.verdict,
            "owner": self.owner,
            "reply": self.desks[self.owner].reply,
            "topic": self.topic,
            "ideas": self.ideas,
            "styles": self.styles,
            "history": self.history,
            "cost_usd": round(self.cost_usd, 4),
            "max_rounds": self.autopilot["max_rounds"],
        }

    def _save_state(self) -> None:
        """Writes the project's state and its summary, only when they changed."""
        with self._lock:
            data = json.dumps(self._remembered(), ensure_ascii=False, indent=1)
            if data == self._saved:
                return
            self._saved = data
            self._keep(lambda: _write_file(self.workspace / STATE_FILE, data))
            self._keep(lambda: _write_file(self.workspace / SUMMARY_FILE, self._summary()))

    def _keep(self, write) -> None:
        # A disk that refuses a write must not stop the office; the work itself is in git.
        try:
            write()
        except OSError as e:
            print(f"Rens Office: could not save to {self.workspace / OFFICE_DIR}: {e}", file=sys.stderr)

    def _load_state(self) -> None:
        """Picks the project up where it was left: the task, its verdict, the ideas and the log."""
        try:
            saved = json.loads((self.workspace / STATE_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = None
        if isinstance(saved, dict):
            self.baseline = self._commit_or_none(saved.get("baseline"))
            if self.baseline:
                # A task, its verdict and the reply only mean something against the change since the baseline.
                self.task = _text(saved.get("task"))
                self.task_title = _text(saved.get("task_title"))
                self.verdict = _verdict(saved.get("verdict"))
                self.owner = saved.get("owner") if saved.get("owner") in DEVELOPERS else "backend"
                self.desks[self.owner].reply = _text(saved.get("reply") or saved.get("worker_reply"))
            self.topic = _text(saved.get("topic"))
            self.ideas = _ideas(saved.get("ideas")) if self.topic else None
            self.styles = _styles(saved.get("styles"))
            self.history = [done for done in saved.get("history") or [] if _done(done)]
            cost = saved.get("cost_usd")
            self.cost_usd = float(cost) if isinstance(cost, (int, float)) else 0.0
            rounds = saved.get("max_rounds")
            if isinstance(rounds, int) and 1 <= rounds <= MAX_ROUNDS:
                self.autopilot["max_rounds"] = rounds
        self._log.extend(_read_log(self.workspace / LOG_FILE))
        self._saved = json.dumps(self._remembered(), ensure_ascii=False, indent=1)

    def _commit_or_none(self, sha) -> str | None:
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{7,64}", sha):
            return None
        try:
            self._git("cat-file", "-e", f"{sha}^{{commit}}")
        except context.ContextError:
            return None  # the history was rewritten since; the next task starts a new baseline
        return sha

    def _summary(self) -> str:
        """Where the project stands, for the person who opens the folder."""
        lines = [
            f"# {self._t('summary_title', project=self.workspace.name)}",
            "",
            self._t("summary_updated", time=_when(time.time())),
            "",
            f"## {self._t('summary_done')}",
        ]
        lines += [f"- {_when(done['time'])} · {done['title']}{_by(done)}" for done in self.history] or [
            self._t("summary_nothing_done")
        ]
        lines += ["", f"## {self._t('summary_now')}"]
        lines += [f"**{self.task_title}**", "", self.task] if self.task else [self._t("summary_no_task")]
        if self.verdict:
            state = "sent" if self.verdict.get("sent") else "approved" if self.verdict["approved"] else "rejected"
            lines += ["", f"## {self._t('summary_review_' + state)}", self.verdict["summary"]]
            lines += [_issue_line(issue) for issue in self.verdict["issues"]]
        if self.ideas:
            lines += ["", f"## {self._t('summary_ideas', topic=self.topic)}"]
            lines += [
                f"- {idea['title']}"
                + (f" ({self._t('summary_idea_handed', name=NAMES[idea['developer']])})" if idea["handed"] else "")
                for idea in self.ideas
            ]
        return "\n".join(lines) + "\n"

    def _project_context(self, with_task: bool) -> str:
        """For an agent starting a fresh conversation in a project with a past: what was done, and
        for a rework the task and its notes. Nothing for a project without one."""
        notes = []
        if self.history:
            notes += [self._t("context_done"), *(f"- {done['title']}{_by(done)}" for done in self.history)]
        if with_task and self.task:
            notes += [self._t("context_task", task=self.task)]
        if not notes:
            return ""
        return self._t("project_context", notes="\n".join(notes)) + "\n\n"

    def _set_agent(self, agent: str, status: str | None = None, bubble: str | None = None) -> None:
        with self._lock:
            if status is not None:
                self.agents[agent]["status"] = status
            if bubble is not None:
                self.agents[agent]["bubble"] = bubble
                self._bubble_src[agent] = None
        self._emit_state()

    def _phrase(self, agent: str, key: str, **values) -> None:
        """Puts a translatable phrase in an agent's bubble, without telling the page yet."""
        with self._lock:
            self.agents[agent]["bubble"] = self._t(key, **values)
            self._bubble_src[agent] = (key, values)

    def _announce(self, agent: str, key: str, status: str | None = None, **values) -> None:
        self._phrase(agent, key, **values)
        self._set_agent(agent, status)

    # ----- git -----

    def _git(self, *args: str) -> str:
        return context.run_git(self.workspace, *args).strip()

    def _ensure_repo(self) -> None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        if not (self.workspace / ".git").exists():
            self._git("init", "-q")
        git_dir = self.workspace / ".git"
        if git_dir.is_dir():
            exclude = git_dir / "info" / "exclude"
            exclude.parent.mkdir(parents=True, exist_ok=True)
            current = exclude.read_text().splitlines() if exclude.exists() else []
            missing = [pattern for pattern in LOCAL_EXCLUDES if pattern not in current]
            if missing:
                with exclude.open("a") as f:
                    f.write("\n# Rens Office: caches are never worth reviewing\n" + "\n".join(missing) + "\n")

    def _commit(self, message: str) -> str:
        self._git("add", "-A")
        self._git(*self._identity(), "commit", "-q", "--allow-empty", "-m", message)
        return self._git("rev-parse", "HEAD")

    def _identity(self) -> list[str]:
        """Commits go out under the user's git name, so GitHub credits them; else under the office's."""
        try:
            name, email = self._git("config", "user.name"), self._git("config", "user.email")
        except context.ContextError:  # git exits with 1 for a setting that is not there
            return OFFICE_GIT_IDENTITY
        return [] if name and email else OFFICE_GIT_IDENTITY

    # ----- actions -----

    def _busy_check(self) -> None:
        # The developers share one folder, so one of them works at a time, and never during a review.
        for dev in DEVELOPERS:
            if self.agents[dev]["status"] == "working":
                raise Busy(self._t("busy_dev", name=NAMES[dev]))
        if self.agents["reviewer"]["status"] == "reviewing":
            raise Busy(self._t("busy_reviewer"))

    def _desk_free(self, developer: str) -> None:
        """A developer at work, or looking for a style, takes nothing else on."""
        if self.agents[developer]["status"] in ("working", "thinking"):
            raise Busy(self._t("busy_dev", name=NAMES[developer]))

    def _building(self) -> bool:
        """Whether a developer or the reviewer is at work, which the autopilot waits for."""
        try:
            self._busy_check()
        except Busy:
            return True
        return False

    def _start(self, target, *args) -> None:
        thread = threading.Thread(target=target, args=args, daemon=True)
        with self._lock:
            # Finished threads are dropped, so the list stays as short as the work in progress.
            self._threads = [t for t in self._threads if t.is_alive()] + [thread]
        thread.start()

    def start_task(
        self, text: str, developer: str = "backend", title: str | None = None, from_idea: bool = False, files=None
    ) -> None:
        text = text.strip()
        if not text:
            raise ValueError(self._t("empty_task"))
        if developer not in DEVELOPERS:
            raise ValueError(self._t("bad_developer"))
        attachments = self._attachments(files)
        with self._lock:
            self._busy_check()
            self._desk_free(developer)
            if self.baseline is None:
                # Everything after this commit is the developers' change, which is what gets reviewed.
                self.baseline = self._commit("office: before task")
            self.task = text
            self.task_title = (title or text.splitlines()[0])[:60]
            self.verdict = None
            self.autopilot["round"] = 0
            self.autopilot["halted"] = None
            self.owner = developer
            self.agents[developer]["status"] = "working"
            self._phrase(developer, "reading_task")
            self._phrase("reviewer", "reviewer_waiting")
            run = self._prepare(developer, text + self._files_note("task_files", attachments))
        if from_idea:
            self._log_entry(
                "ideator", "handoff", self._t("log_idea_handoff", name=NAMES[developer], title=self.task_title)
            )
        else:
            self._log_entry("user", "task", self._t("log_task", name=NAMES[developer], text=text) + _file_names(attachments))
        self._emit_state()
        self._start(self._work, developer, run)

    def send_rework(self) -> None:
        with self._lock:
            self._busy_check()
            if not self.verdict or (self.verdict["approved"] and not self.verdict["issues"]):
                raise ValueError(self._t("nothing_to_fix"))
            if self.verdict.get("sent"):
                raise ValueError(self._t("already_sent"))
            self._desk_free(self.owner)
            prompt = rework_prompt(self.verdict, self.lang)
            # The verdict stays visible as the list being fixed, but it describes the old version now.
            self.verdict["sent"] = True
            developer = self.owner
            self.agents[developer]["status"] = "working"
            self._phrase(developer, "reading_findings")
            self.agents["reviewer"]["status"] = "idle"
            self._phrase("reviewer", "waiting_for_fixes")
            run = self._prepare(developer, prompt, with_task=True)
        self._log_entry("reviewer", "handoff", self._t("log_handoff", name=NAMES[developer]))
        self._emit_state()
        self._start(self._work, developer, run)

    def request_review(self, auto: bool = False) -> None:
        with self._lock:
            self._busy_check()
            if self.baseline is None:
                raise ValueError(self._t("no_task_yet"))
            # On a re-review the reviewer checks that its earlier notes were fixed.
            previous = self.verdict["issues"] if self.verdict and self.verdict.get("sent") else None
            # Also when the verdict had no notes, only failing checks: the reply says what was done about them.
            reply = self.desks[self.owner].reply if previous is not None else None
            self.agents["reviewer"]["status"] = "reviewing"
            self._phrase("reviewer", "looking_at_changes")
        if auto:
            self._log_entry("office", "auto", self._t("autopilot_review"))
        else:
            self._log_entry("user", "request", self._t("log_review_request"))
        self._emit_state()
        self._start(self._review, previous, reply)

    def accept(self) -> None:
        with self._lock:
            self._busy_check()
            if self.baseline is None:
                raise ValueError(self._t("nothing_to_accept"))
            self.baseline = self._commit(f"office: accepted: {self.task_title or 'work'}")
            self.history.append(
                {"title": self.task_title or "work", "commit": self.baseline, "time": time.time(), "by": self.owner}
            )
            # Accepted work is done; the next task, or the next idea, starts from this commit.
            self.task = None
            self.task_title = None
            self.verdict = None
            for desk in self.desks.values():
                desk.reply = None  # their reports are about work that is now done
            self._phrase(self.owner, "accepted_waiting")
            self.agents["reviewer"]["status"] = "idle"
            self._phrase("reviewer", "reviewer_waiting")
        self._log_entry("user", "accept", self._t("log_accept", commit=self.baseline[:8]))
        self._emit_state()

    def stop(self, agent: str) -> None:
        if agent not in (*DEVELOPERS, "ideator"):
            raise ValueError(self._t("cannot_stop"))
        with self._lock:
            run = self._ideator_run if agent == "ideator" else self.desks[agent].run
        if run is None:
            raise ValueError(self._t("not_running", name=NAMES[agent]))
        run.stop()

    def shutdown(self, grace: float = STOP_GRACE_SECONDS) -> None:
        """Stops every agent and check, so nothing runs or edits files after the office is gone.

        Runs that start later (the autopilot, a request already under way) are stopped as they start.
        """
        with self._lock:
            self._closed = True
            runs = [
                r
                for r in (*(desk.run for desk in self.desks.values()), self._ideator_run, self._review_run, self._limits_run)
                if r is not None
            ]
            check = self._check_proc
        for run in runs:
            run.stop()
        if check is not None:
            kill_tree(check, force=True)
        # The office exits next, so the runs get a moment to end and are then ended outright.
        self.wait_idle(grace)
        for run in runs:
            run.kill()

    def close(self) -> None:
        """Lets the project go: its work stops, its state is saved, and the pages showing it reload."""
        self.shutdown()
        self._save_state()
        self._broadcast({"type": "reload"})

    def refresh_limits(self) -> None:
        """Reads the subscription's limits with one tiny request, unless a check is under way."""
        with self._lock:
            if self._limits_run is not None or self._closed:
                return
            run = self._limits_run = ClaudeCodeRun(
                ".",
                cwd=self.workspace,
                tools=[],
                system_prompt=LIMITS_CHECK_PROMPT,
                model=LIMITS_CHECK_MODEL,
                persist_session=False,
            )
        self._emit_state()
        self._start(self._check_limits, run)

    def _check_limits(self, run: ClaudeCodeRun) -> None:
        try:
            run.run(self._on_limits_check_event)
        except ClaudeCodeStopped:
            pass
        except Exception as e:
            # The limits are a convenience: a failed check only leaves them unknown.
            self._log_entry("office", "error", self._t("limits_failed", error=str(e)))
        finally:
            with self._lock:
                self._limits_run = None
            self._emit_state()

    def _on_limits_check_event(self, event: dict) -> None:
        if event.get("type") == "rate_limit_event":
            self._update_limits(event.get("rate_limit_info"))

    def _update_limits(self, info) -> None:
        windows = limit_windows(info)
        if windows:
            with self._lock:
                self.limits = windows
            self._emit_state()

    def _track_review(self, run: ClaudeCodeRun) -> None:
        with self._lock:
            self._review_run = run
            if self._closed:
                run.stop()

    def _track_check(self, proc) -> None:
        with self._lock:
            self._check_proc = proc
            closed = self._closed
        if closed:
            kill_tree(proc, force=True)

    def generate_ideas(self, topic: str, files=None) -> None:
        topic = topic.strip()
        if not topic:
            raise ValueError(self._t("empty_topic"))
        attachments = self._attachments(files)
        with self._lock:
            # The idea maker only reads, so it may think while the others work.
            if self.agents["ideator"]["status"] == "thinking":
                raise Busy(self._t("busy_ideator"))
            self.agents["ideator"]["status"] = "thinking"
            self._phrase("ideator", "ideator_thinking", topic=_shorten(topic, 40))
            notes = self._files_note("topic_files", attachments)
            if self._ideator_session is None and self.ideas:
                # A fresh conversation does not know the ideas this project already has.
                notes += "\n\n" + self._t("ideas_before", titles="; ".join(idea["title"] for idea in self.ideas))
            run = self._ideator_run = ClaudeCodeRun(
                # Like the developers', every message of the resumed conversation names the language.
                idea_request(topic, self._t("reply_in"), notes),
                cwd=self.workspace,
                tools=IDEATOR_TOOLS,
                system_prompt=IDEATOR_PROMPT,
                json_schema=IdeasOutput.model_json_schema(),
                model=self._model("ideator"),
                effort=self._effort("ideator"),
                resume=self._ideator_session,
                plugin_dirs=self._plugin_dirs["ideator"],
            )
            if self._closed:
                run.stop()
        self._log_entry("user", "topic", self._t("log_topic", topic=topic) + _file_names(attachments))
        self._emit_state()
        self._start(self._ideate, run, topic)

    # ----- frontren's style directions -----

    def propose_styles(self, brief: str, files=None) -> None:
        """frontren looks for references and proposes a few styles; it only reads, so backren may work meanwhile."""
        brief = brief.strip()
        attachments = self._attachments(files)
        with self._lock:
            self._desk_free("frontend")
            self.agents["frontend"]["status"] = "thinking"
            self._phrase("frontend", "styles_thinking")
            notes = self._files_note("style_files", attachments)
            if self.styles:
                names = "; ".join(d["name"] for d in self.styles["directions"])
                notes += "\n\n" + self._t("styles_before", names=names)
            desk = self.desks["frontend"]
            run = desk.run = ClaudeCodeRun(
                style_request(brief, self.task, self._t("reply_in"), notes),
                cwd=self.workspace,
                tools=STYLE_TOOLS,
                system_prompt=STYLE_PROMPT,
                json_schema=StylesOutput.model_json_schema(),
                model=self._model("frontend"),
                effort=self._effort("frontend"),
                persist_session=False,
                plugin_dirs=self._plugin_dirs["frontend"],
                mcp_tools=figma_tools(brief, self.task),
            )
            if self._closed:
                run.stop()
        self._log_entry("user", "styles", self._t("log_styles", brief=brief or "—") + _file_names(attachments))
        self._emit_state()
        self._start(self._find_styles, run, brief)

    def choose_style(self, index) -> None:
        """Writes the chosen direction to DESIGN.md, which frontren follows from then on."""
        with self._lock:
            if not self.styles:
                raise ValueError(self._t("no_styles"))
            try:
                n = int(index)
            except (TypeError, ValueError):
                raise ValueError(self._t("bad_style")) from None
            if not 0 <= n < len(self.styles["directions"]):
                raise ValueError(self._t("bad_style"))
            # A developer at work may be reading the file, and a review would see it change midway.
            self._busy_check()
            direction = self.styles["directions"][n]
            # A project file: the developers build from it, and checkren sees it in the change.
            try:
                _write_file(self.workspace / DESIGN_FILE, design_md(direction))
            except OSError as e:  # say, the file is open in an editor that locks it (Windows)
                raise ValueError(self._t("design_not_saved", error=e.strerror or e)) from None
            self.styles["chosen"] = n
            if self.agents["frontend"]["status"] != "thinking":
                self._phrase("frontend", "style_chosen", name=_shorten(direction["name"], 40))
        self._log_entry("user", "style", self._t("log_style_chosen", name=direction["name"]))
        self._emit_state()

    def _find_styles(self, run: ClaudeCodeRun, brief: str) -> None:
        desk = self.desks["frontend"]
        try:
            result = run.run(lambda e: self._on_agent_event("frontend", e, keep_session=False))
            directions, best = parse_styles(result.structured_output)
        except Exception as e:
            # Like any run, it must end in "idle", or frontren could never get a task again.
            stopped = isinstance(e, ClaudeCodeStopped)
            self._log_entry("frontend", "error", self._t("log_stopped") if stopped else str(e))
            with self._lock:
                self.agents["frontend"]["skill"] = None
            self._announce("frontend", "stopped" if stopped else "went_wrong", "idle")
        else:
            with self._lock:
                self.styles = {"brief": brief, "directions": directions, "recommended": best, "chosen": None}
                self.cost_usd += result.cost_usd or 0
                self.agents["frontend"]["skill"] = None
            names = "; ".join(d["name"] for d in directions)
            self._log_entry("frontend", "styles", self._t("log_styles_ready", n=len(directions), names=names))
            self._announce("frontend", "styles_ready", "idle", n=len(directions))
        finally:
            with self._lock:
                if desk.run is run:
                    desk.run = None
        # The autopilot may have waited for frontren: notes to send back, or an idea to hand over.
        self._autopilot_step()
        self._autopilot_handoff()

    def save_upload(self, name: str, data) -> str:
        """Keeps a file the user hands the agents, sent as base64; returns its name in the uploads folder."""
        try:
            content = base64.b64decode(data, validate=True)
        except (binascii.Error, TypeError, ValueError):
            raise ValueError(self._t("bad_upload")) from None
        if len(content) > MAX_UPLOAD_BYTES:
            raise ValueError(self._t("upload_too_big", mb=MAX_UPLOAD_BYTES // 2**20))
        folder = self.workspace / UPLOADS_DIR
        stem, suffix = os.path.splitext(safe_file_name(name))
        try:
            folder.mkdir(parents=True, exist_ok=True)
            for n in itertools.count(1):
                target = folder / (f"{stem}{suffix}" if n == 1 else f"{stem} ({n}){suffix}")
                try:
                    file = target.open("xb")  # never replaces a file, not even with two uploads at once
                except FileExistsError:
                    continue
                try:
                    with file:
                        file.write(content)
                except OSError:
                    target.unlink(missing_ok=True)  # half a file would pass for the whole one
                    raise
                return target.name
        except OSError as e:
            # A full disk or a locked folder: the page says so instead of a server error.
            raise ValueError(self._t("upload_failed", name=stem + suffix, error=e.strerror or e)) from None

    def _attachments(self, files) -> list[Path]:
        """The uploaded files a task or a topic names, each checked to be in the uploads folder."""
        if not files:
            return []
        folder = self.workspace / UPLOADS_DIR
        if not isinstance(files, list) or not all(
            isinstance(name, str) and safe_file_name(name) == name and (folder / name).is_file() for name in files
        ):
            raise ValueError(self._t("missing_upload"))
        return [folder / name for name in files]

    def _files_note(self, key: str, files: list[Path]) -> str:
        """Where the attached files are, for the agent's prompt; Claude Code's Read wants full paths."""
        if not files:
            return ""
        return "\n\n" + self._t(key, files="\n".join(f"- {path}" for path in files))

    def hand_off(self, index, developer: str | None = None) -> None:
        """Gives one of the ideas to a developer as the next task: the one idearen picked, unless named."""
        with self._lock:
            if not self.ideas:
                raise ValueError(self._t("no_ideas"))
            try:
                n = int(index)
            except (TypeError, ValueError):
                raise ValueError(self._t("bad_idea")) from None
            if not 0 <= n < len(self.ideas):
                raise ValueError(self._t("bad_idea"))
            self._busy_check()
            idea = self.ideas[n]
            developer = developer or idea["developer"]
            text = task_from_idea(idea, self.topic or "", self._t("idea_intro"), self._t("idea_guard"))
            self.start_task(text, developer, title=idea["title"], from_idea=True)
            idea["handed"] = True
            idea["developer"] = developer
            self._phrase("ideator", "handed_off", name=NAMES[developer], title=_shorten(idea["title"], 40))
        self._emit_state()

    def set_autopilot(self, enabled: bool, max_rounds: int | None = None) -> None:
        with self._lock:
            if max_rounds is not None:
                try:
                    rounds = int(max_rounds)
                except (TypeError, ValueError):
                    raise ValueError(self._t("bad_rounds")) from None
                if not 1 <= rounds <= MAX_ROUNDS:
                    raise ValueError(self._t("bad_rounds"))
                self.autopilot["max_rounds"] = rounds
            turned_on = enabled and not self.autopilot["enabled"]
            turned_off = not enabled and self.autopilot["enabled"]
            self.autopilot["enabled"] = bool(enabled)
            if turned_on:
                self.autopilot["round"] = 0
                self.autopilot["halted"] = None
        if turned_on:
            self._log_entry("office", "auto", self._t("autopilot_on", max=self.autopilot["max_rounds"]))
        elif turned_off:
            self._log_entry("office", "auto", self._t("autopilot_off"))
        self._emit_state()
        if turned_on:
            # Pick up from wherever the work is now: a task in progress, or ideas waiting for one.
            self._autopilot_step()
            self._autopilot_handoff()

    def _autopilot_step(self) -> None:
        """Takes the next step of the work -> review -> fixes loop, if the autopilot is on."""
        with self._lock:
            pilot = self.autopilot
            # A closed office starts nothing: a run that ends as it closes must not set off the next one.
            if not pilot["enabled"] or pilot["halted"] or self.task is None or self._building() or self._closed:
                return
            verdict = self.verdict
            if verdict is None or verdict.get("sent"):
                action = "review"
            elif verdict["approved"]:
                pilot["halted"] = "approved"
                action = "done"
            elif pilot["round"] >= pilot["max_rounds"]:
                pilot["halted"] = "limit"
                action = "limit"
            elif self.agents[self.owner]["status"] == "thinking":
                return  # the notes wait for frontren's style search, which steps the loop on when it ends
            else:
                pilot["round"] += 1
                action = "rework"
            rounds, limit = pilot["round"], pilot["max_rounds"]

        try:
            if action == "review":
                self.request_review(auto=True)
            elif action == "rework":
                self._log_entry("office", "auto", self._t("autopilot_round", round=rounds, max=limit))
                self.send_rework()
            elif action == "done":
                self._log_entry("office", "auto", self._t("autopilot_done", rounds=rounds))
                self._emit_state()
            else:
                self._log_entry("office", "auto", self._t("autopilot_limit", max=limit))
                self._emit_state()
        except (Busy, ValueError):
            # Someone else started something in between; the next finished run steps again.
            pass

    def _autopilot_handoff(self) -> None:
        """With the autopilot on, fresh ideas go to the developer when the office is free."""
        with self._lock:
            if (
                not self.autopilot["enabled"] or not self.ideas or self.task is not None
                or self._building() or self._closed
            ):
                return
            best = next((n for n, i in enumerate(self.ideas) if i["recommended"] and not i["handed"]), None)
            if best is None or self.agents[self.ideas[best]["developer"]]["status"] == "thinking":
                return  # a developer looking for a style takes the idea when its search ends
        self._log_entry("office", "auto", self._t("autopilot_idea"))
        try:
            self.hand_off(best)
        except (Busy, ValueError):
            pass

    def _halt_autopilot(self, reason: str) -> None:
        with self._lock:
            if not self.autopilot["enabled"] or self.autopilot["halted"]:
                return
            self.autopilot["halted"] = reason
        self._log_entry("office", "auto", self._t(f"autopilot_{reason}"))
        self._emit_state()

    # ----- agent loops -----

    def _prepare(self, developer: str, prompt: str, with_task: bool = False) -> ClaudeCodeRun:
        """Sets up a developer's next run; called under the lock, with its status set to working.

        The run exists before its thread starts, so Stop works from the first moment. A fresh
        conversation in a project with a past starts from the office's notes on it, and
        `with_task` adds the current task, which a rework's notes alone don't say. A developer
        who picks up the other one's unaccepted work hears that developer's report on it, once.
        """
        desk = self.desks[developer]
        desk.reply = None
        other = next(dev for dev in DEVELOPERS if dev != developer)
        if report := self.desks[other].reply:
            prompt = self._t("teammate_report", name=NAMES[other], report=report) + "\n\n" + prompt
            self.desks[other].reply = None
        if desk.session_id is None:
            prompt = self._project_context(with_task) + prompt
        desk.run = ClaudeCodeRun(
            # The language goes in every message: a resumed session keeps its original system prompt.
            f"{prompt}\n\n{self._t('reply_in')}",
            cwd=self.workspace,
            tools=self.developer_tools + EXTRA_TOOLS[developer],
            append_system_prompt=DEVELOPER_PROMPTS[developer],
            model=self._model(developer),
            effort=self._effort(developer),
            resume=desk.session_id,
            accept_edits=True,
            plugin_dirs=self._plugin_dirs[developer],
            # A rework's notes don't repeat the link, but the task it fixes does.
            mcp_tools=figma_tools(prompt, self.task) if developer == "frontend" else None,
        )
        if self._closed:
            desk.run.stop()
        return desk.run

    def _work(self, developer: str, run: ClaudeCodeRun) -> None:
        desk = self.desks[developer]
        try:
            result = run.run(lambda e: self._on_agent_event(developer, e))
        except Exception as e:
            # Any failure must end in "idle": a stuck "working" would block the office for good.
            stopped = isinstance(e, ClaudeCodeStopped)
            self._log_entry(developer, "error", self._t("log_stopped") if stopped else str(e))
            with self._lock:
                self.agents[developer]["skill"] = None
            self._announce(developer, "stopped" if stopped else "went_wrong", "idle")
            self._halt_autopilot("stopped" if stopped else "error")
            return
        finally:
            with self._lock:
                if desk.run is run:  # a new task may already have its own run
                    desk.run = None

        with self._lock:
            desk.session_id = result.session_id or desk.session_id
            desk.reply = result.text or None
            self.cost_usd += result.cost_usd or 0
            self.agents[developer]["skill"] = None
        if result.text:
            self._log_entry(developer, "result", result.text)
        self._announce(developer, "done", "idle")
        self._autopilot_step()

    def _ideate(self, run: ClaudeCodeRun, topic: str) -> None:
        try:
            result = run.run(lambda e: self._on_agent_event("ideator", e))
            ideas = parse_ideas(result.structured_output)
        except Exception as e:
            # As with the developer, a failure must never leave "thinking" behind.
            stopped = isinstance(e, ClaudeCodeStopped)
            self._log_entry("ideator", "error", self._t("log_stopped") if stopped else str(e))
            with self._lock:
                self.agents["ideator"]["skill"] = None
            self._announce("ideator", "stopped" if stopped else "ideas_failed", "idle")
            return
        finally:
            with self._lock:
                if self._ideator_run is run:
                    self._ideator_run = None

        with self._lock:
            self._ideator_session = result.session_id or self._ideator_session
            self.cost_usd += result.cost_usd or 0
            # The topic changes together with its ideas, so a stopped or failed run leaves both as they were.
            self.topic = topic
            self.ideas = ideas
            self.agents["ideator"]["skill"] = None
        titles = "; ".join(idea["title"] for idea in ideas)
        self._log_entry("ideator", "ideas", self._t("log_ideas", count=len(ideas), topic=topic, titles=titles))
        self._announce("ideator", "ideas_ready", "ready", count=len(ideas))
        self._autopilot_handoff()

    def _review(self, previous: list[dict] | None = None, reply: str | None = None) -> None:
        try:
            ctx = context.collect_diff(self.workspace, base=self.baseline)
            config = load_config(self.workspace)
            checks = config.get("checks", [])
            if checks and "Bash" not in self.developer_tools:
                # The developers can still edit .ai-review.toml, so without Bash its commands must not run either.
                self._log_entry("reviewer", "check", self._t("checks_skipped"))
                checks = []
            for command in checks:
                self._announce("reviewer", "running", command=command[:60])
                try:
                    check = context.run_check(command, self.workspace, on_start=self._track_check)
                finally:
                    with self._lock:
                        self._check_proc = None
                ctx.checks.append(check)
                self._log_entry("reviewer", "check", f"{'✓' if check.passed else '✗'} {command}")

            failed = [c for c in ctx.checks if not c.passed]
            if failed and config.get("fast_fail", True):
                # Broken checks mean the code will change anyway, so a full model review would be wasted.
                verdict = fast_fail_verdict(failed, self.lang)
                phrase = ("fast_fail_bubble", {})
            else:
                self._announce("reviewer", "reading_changes")
                language = REVIEW_LANGUAGE.format(language=self._t("language_name"))
                hint = REVIEWER_SKILLS_HINT if self._plugin_dirs["reviewer"] else None
                instructions = "\n\n".join(
                    filter(None, [config.get("instructions"), REVIEWER_PERSONA, hint, language])
                )
                try:
                    verdict = review(
                        ctx,
                        backend="claude-code",
                        model=self._model("reviewer"),
                        effort=self._effort("reviewer") or config.get("effort") or DEFAULT_EFFORT,
                        instructions=instructions,
                        cwd=self.workspace,
                        on_event=lambda e: self._on_agent_event("reviewer", e),
                        plugin_dirs=self._plugin_dirs["reviewer"],
                        previous=previous,
                        developer_reply=reply,
                        on_run=self._track_review,
                    )
                finally:
                    with self._lock:
                        self._review_run = None
                blocking = sum(1 for i in verdict.issues if i.severity in BLOCKING)
                if verdict.approved:
                    phrase = ("approved", {})
                else:
                    phrase = ("needs_fixes", {"count": blocking}) if blocking else ("checks_failed", {})
        except Exception as e:
            # A stuck "reviewing" would block the office, so every failure ends the review.
            self._log_entry("reviewer", "error", str(e))
            with self._lock:
                self.agents["reviewer"]["skill"] = None
            self._announce("reviewer", "review_failed", "idle")
            self._halt_autopilot("error")
            return

        data = verdict_to_dict(verdict, ctx)
        with self._lock:
            self.verdict = data
            self.cost_usd += verdict.cost_usd or 0
            self.agents["reviewer"]["skill"] = None
        self._log_entry("reviewer", "verdict", verdict.summary)
        self._announce("reviewer", phrase[0], "approved" if verdict.approved else "rejected", **phrase[1])
        self._autopilot_step()

    def _on_agent_event(self, agent: str, event: dict, keep_session: bool = True) -> None:
        if event.get("type") == "system" and event.get("subtype") == "init":
            # A developer's run continues its conversation; a style search is a one-off.
            if agent in DEVELOPERS and keep_session:
                with self._lock:
                    desk = self.desks[agent]
                    desk.session_id = event.get("session_id") or desk.session_id
            return
        if event.get("type") == "rate_limit_event":
            self._update_limits(event.get("rate_limit_info"))
            return
        if event.get("type") != "assistant":
            return
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "tool_use":
                args = block.get("input") or {}
                text = describe_tool(block.get("name", ""), args, self.lang)
                if block.get("name") == "Skill":
                    with self._lock:
                        self.agents[agent]["skill"] = skill_name(args)
                self._log_entry(agent, "skill" if block.get("name") == "Skill" else "tool", text)
                self._set_agent(agent, bubble=text)
            elif block.get("type") == "text" and block.get("text", "").strip():
                text = block["text"].strip()
                self._log_entry(agent, "say", text)
                self._set_agent(agent, bubble=_shorten(text))

    def wait_idle(self, timeout: float = 10) -> None:
        """Waits until no agent thread is running, including ones the autopilot starts."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                alive = [thread for thread in self._threads if thread.is_alive()]
            if not alive:
                return
            alive[0].join(max(0.0, deadline - time.monotonic()))


def safe_file_name(name: str) -> str:
    """`name` as a plain file name: no folders, nothing Windows refuses, not too long."""
    base = re.split(r"[\\/]", name)[-1]
    base = re.sub(r'[<>:"|?*\x00-\x1f]', "_", base).strip(" ").rstrip(".")
    stem, suffix = os.path.splitext(base)
    if stem.upper() in WINDOWS_RESERVED:
        stem = f"_{stem}"
    return stem[:100] + suffix[:20] or "file"


def _write_file(path: Path, text: str) -> None:
    """Replaces a file in one step, so a crash halfway leaves the old one, not half of the new."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _read_log(path: Path) -> list[dict]:
    """The last LOG_LIMIT entries of a project's log; a log that grew far past that is cut back."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entries = []
    for line in lines[-LOG_LIMIT:]:
        try:
            entry = json.loads(line)
        except ValueError:
            continue  # a line cut short when the office was killed mid-write
        if isinstance(entry, dict) and all(isinstance(entry.get(k), str) for k in ("agent", "kind", "text")) \
                and isinstance(entry.get("time"), (int, float)):
            entries.append(entry)
    if len(lines) > 2 * LOG_LIMIT:
        try:
            _write_file(path, "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))
        except OSError:
            pass  # it is read the same way next time
    return entries


def _text(value) -> str | None:
    return value if isinstance(value, str) and value else None


def _verdict(value) -> dict | None:
    ok = (
        isinstance(value, dict)
        and isinstance(value.get("approved"), bool)
        and isinstance(value.get("summary"), str)
        and isinstance(value.get("reasons"), list)
        and isinstance(value.get("checks"), list)
        and isinstance(value.get("issues"), list)
        and all(_issue(issue) for issue in value["issues"])
    )
    return value if ok else None


def _issue(value) -> bool:
    return (
        isinstance(value, dict)
        and value.get("severity") in ("critical", "major", "minor", "nit")
        and all(isinstance(value.get(k), str) for k in ("file", "title", "explanation", "suggestion"))
        and isinstance(value.get("line"), int)
    )


def _ideas(value) -> list[dict] | None:
    if not isinstance(value, list):
        return None
    ideas = [
        # Ideas saved before there were two developers name neither a developer nor an interface.
        {"developer": "backend", "ui": "", **idea}
        for idea in value
        if isinstance(idea, dict)
        and all(isinstance(idea.get(k), str) for k in ("title", "pitch", "why", "task"))
        and idea.get("scope") in ("small", "medium", "large")
        and idea.get("developer", "backend") in DEVELOPERS
        and isinstance(idea.get("ui", ""), str)
        and isinstance(idea.get("recommended"), bool)
        and isinstance(idea.get("handed"), bool)
    ]
    return ideas or None


def _styles(value) -> dict | None:
    """frontren's saved style directions, checked like a fresh answer; None if they no longer hold."""
    if not isinstance(value, dict) or not isinstance(value.get("directions"), list):
        return None
    try:
        directions, best = parse_styles({"directions": value["directions"], "recommended": value.get("recommended", 0)})
    except StylesError:
        return None
    if len(directions) != len(value["directions"]):
        return None  # a direction was dropped, so the chosen index may point at another one
    chosen = value.get("chosen")
    brief = value.get("brief")
    return {
        "brief": brief if isinstance(brief, str) else "",
        "directions": directions,
        "recommended": best,
        "chosen": chosen if isinstance(chosen, int) and 0 <= chosen < len(directions) else None,
    }


def _done(value) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("title"), str)
        and isinstance(value.get("commit"), str)
        and isinstance(value.get("time"), (int, float))
        and value.get("by", "backend") in DEVELOPERS
    )


def _by(done: dict) -> str:
    """Who built an accepted task, for the notes: entries from before two developers have no `by`."""
    return f" ({NAMES[done['by']]})" if "by" in done else ""


def _when(timestamp: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(timestamp))


def _issue_line(issue: dict) -> str:
    where = f"{issue['file']}:{issue['line']}" if issue["line"] else issue["file"]
    return f"- [{issue['severity']}] {where + ' ' if where else ''}{issue['title']}"


def _file_names(files: list[Path]) -> str:
    """The attached files, as a line under the task or topic in the log."""
    return "\n📎 " + ", ".join(path.name for path in files) if files else ""


def limit_windows(info) -> list[dict]:
    """The usage limit windows in a Claude Code rate_limit_event: how much is used and when it resets.

    `used` is a share of the window (0.28 is 28%), `resets_at` a Unix time. Anything unexpected
    gives no windows: the gauge must never stop an agent's run.
    """
    windows = info.get("unifiedWindows") if isinstance(info, dict) else None
    if not isinstance(windows, dict):
        return []
    result = [
        {"name": name, "used": window["utilization"], "resets_at": window.get("resetsAt"), "status": window.get("status")}
        for name, window in windows.items()
        if isinstance(window, dict) and isinstance(window.get("utilization"), (int, float))
    ]
    order = {name: n for n, name in enumerate(LIMIT_WINDOWS)}
    return sorted(result, key=lambda window: order.get(window["name"], len(order)))


def verdict_to_dict(verdict: Verdict, ctx: context.ReviewContext) -> dict:
    data = asdict(verdict)
    data["issues"] = [i.model_dump() for i in verdict.issues]
    data["checks"] = [{"command": c.command, "passed": c.passed} for c in ctx.checks]
    return data


def _shorten(text: str, limit: int = 90) -> str:
    first = next(iter(text.strip().splitlines()), "")
    return first if len(first) <= limit else first[: limit - 1] + "…"
