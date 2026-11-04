"""The office: an idea maker, a worker that writes code, and a reviewer that checks it."""

from __future__ import annotations

import queue
import subprocess
import threading
import time
from collections import deque
from dataclasses import asdict
from pathlib import Path

from reviewer import context
from reviewer.claude_code import ClaudeCodeError, ClaudeCodeRun
from reviewer.cli import ConfigError, load_config
from reviewer.llm import BLOCKING, Issue, ReviewError, Verdict, review

from .i18n import LANGUAGES, has, t
from .ideator import (
    IDEATOR_PROMPT,
    IDEATOR_TOOLS,
    IdeasError,
    IdeasOutput,
    idea_request,
    parse_ideas,
    task_from_idea,
)

WORKER_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "Skill"]

# Each role's skills are a Claude Code plugin, loaded only into that agent's runs.
SKILLS_DIR = Path(__file__).parent / "skills"
ROLES = ("worker", "reviewer", "ideator")

WORKER_PROMPT = """\
You are coderen, the developer in a three-person office: idearen comes up with ideas, you build \
them in the current directory, and checkren reviews your work. When you receive review findings, \
fix every critical and major issue, and the minor ones where the fix is clear.
Before you start, load the skills that match the request with the Skill tool: test-first for any \
behavior change, project-setup for a new project, frontend-ui and frontend-verify for anything with \
a user interface, address-review when the request contains review notes. Always load self-check \
and follow it before your final message.
Each request ends with the language to reply in; use it for every message to the user. \
When you finish, say in two or three sentences what you did and how to run or test it.
"""

REVIEWER_PERSONA = (
    "In this office you are checkren, the reviewer. The developer whose work you check is coderen; "
    "the ideas come from idearen."
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
    "node_modules/", ".venv/", "venv/", ".DS_Store",
]

REVIEW_LANGUAGE = "Write the summary and every issue's title, explanation and suggestion in {language}."

LOG_LIMIT = 500
FAST_FAIL_OUTPUT_CHARS = 2500
DEFAULT_ROUNDS = 3
MAX_ROUNDS = 10


class Busy(Exception):
    pass


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
    """`worker-skills:test-first` -> `test-first`."""
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


def load_skills(role: str) -> list[dict]:
    """Names and descriptions of a role's skills, read from their SKILL.md front matter."""
    skills = []
    for path in sorted((SKILLS_DIR / role / "skills").glob("*/SKILL.md")):
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
        worker_tools: list[str] | None = None,
        lang: str = "en",
        skills: bool = True,
    ):
        if lang not in LANGUAGES:
            raise ValueError(f"unknown language: {lang}")
        self.lang = lang
        self.workspace = workspace
        self.model = model
        self.effort = effort
        self.worker_tools = worker_tools if worker_tools is not None else WORKER_TOOLS
        self.skills = {role: load_skills(role) if skills else [] for role in ROLES}
        self._plugin_dirs = {role: [SKILLS_DIR / role] if skills else [] for role in ROLES}

        self._lock = threading.RLock()
        self._subscribers: list[queue.Queue] = []
        self._log: deque[dict] = deque(maxlen=LOG_LIMIT)
        self._worker_run: ClaudeCodeRun | None = None
        self._ideator_run: ClaudeCodeRun | None = None
        # The idea maker keeps one conversation, so asking again on a topic brings new ideas.
        self._ideator_session: str | None = None
        self._threads: list[threading.Thread] = []

        self.agents = {
            "worker": {"status": "idle", "bubble": self._t("worker_waiting"), "skill": None},
            "reviewer": {"status": "idle", "bubble": self._t("reviewer_waiting"), "skill": None},
            "ideator": {"status": "idle", "bubble": self._t("ideator_waiting"), "skill": None},
        }
        # The phrase behind each bubble, so a language switch can say it again; None for live text.
        self._bubble_src: dict[str, tuple[str, dict] | None] = {
            "worker": ("worker_waiting", {}),
            "reviewer": ("reviewer_waiting", {}),
            "ideator": ("ideator_waiting", {}),
        }
        self.session_id: str | None = None
        self.baseline: str | None = None
        self.task: str | None = None
        self.task_title: str | None = None
        self.verdict: dict | None = None
        self.topic: str | None = None
        self.ideas: list[dict] | None = None
        self.cost_usd = 0.0
        # halted: why the current autopilot run ended ("approved", "limit", "error", "stopped").
        self.autopilot = {"enabled": False, "max_rounds": DEFAULT_ROUNDS, "round": 0, "halted": None}

        self._ensure_repo()

    # ----- state and events -----

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "agents": {k: dict(v) for k, v in self.agents.items()},
                "task": self.task,
                "verdict": self.verdict,
                "workspace": str(self.workspace),
                "cost_usd": round(self.cost_usd, 4),
                "topic": self.topic,
                "ideas": [dict(idea) for idea in self.ideas] if self.ideas else None,
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
        self._broadcast({"type": "state", "state": self.snapshot()})

    def _log_entry(self, agent: str, kind: str, text: str) -> None:
        entry = {"agent": agent, "kind": kind, "text": text, "time": time.time()}
        with self._lock:
            self._log.append(entry)
        self._broadcast({"type": "log", "entry": entry})

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
        proc = subprocess.run(
            ["git", "-c", "user.name=AI Office", "-c", "user.email=office@localhost", *args],
            cwd=self.workspace,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise context.ContextError(f"git {args[0]} failed: {proc.stderr.strip()}")
        return proc.stdout.strip()

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
                    f.write("\n# AI Office: caches are never worth reviewing\n" + "\n".join(missing) + "\n")

    def _commit(self, message: str) -> str:
        self._git("add", "-A")
        self._git("commit", "-q", "--allow-empty", "-m", message)
        return self._git("rev-parse", "HEAD")

    # ----- actions -----

    def _busy_check(self) -> None:
        if self.agents["worker"]["status"] == "working":
            raise Busy(self._t("busy_worker"))
        if self.agents["reviewer"]["status"] == "reviewing":
            raise Busy(self._t("busy_reviewer"))

    def _start(self, target, *args) -> None:
        thread = threading.Thread(target=target, args=args, daemon=True)
        with self._lock:
            # Finished threads are dropped, so the list stays as short as the work in progress.
            self._threads = [t for t in self._threads if t.is_alive()] + [thread]
        thread.start()

    def start_task(self, text: str, title: str | None = None, from_idea: bool = False) -> None:
        text = text.strip()
        if not text:
            raise ValueError(self._t("empty_task"))
        with self._lock:
            self._busy_check()
            if self.baseline is None:
                # Everything after this commit is the worker's change, which is what gets reviewed.
                self.baseline = self._commit("office: before task")
            self.task = text
            self.task_title = (title or text.splitlines()[0])[:60]
            self.verdict = None
            self.autopilot["round"] = 0
            self.autopilot["halted"] = None
            self.agents["worker"]["status"] = "working"
            self._phrase("worker", "reading_task")
            self._phrase("reviewer", "reviewer_waiting")
        if from_idea:
            self._log_entry("ideator", "handoff", self._t("log_idea_handoff", title=self.task_title))
        else:
            self._log_entry("user", "task", text)
        self._emit_state()
        self._start(self._work, text)

    def send_rework(self, auto: bool = False) -> None:
        with self._lock:
            self._busy_check()
            if not self.verdict or (self.verdict["approved"] and not self.verdict["issues"]):
                raise ValueError(self._t("nothing_to_fix"))
            if self.verdict.get("sent"):
                raise ValueError(self._t("already_sent"))
            prompt = rework_prompt(self.verdict, self.lang)
            # The verdict stays visible as the list being fixed, but it describes the old version now.
            self.verdict["sent"] = True
            self.agents["worker"]["status"] = "working"
            self._phrase("worker", "reading_findings")
            self.agents["reviewer"]["status"] = "idle"
            self._phrase("reviewer", "waiting_for_fixes")
        self._log_entry("reviewer", "handoff", self._t("log_handoff"))
        self._emit_state()
        self._start(self._work, prompt)

    def request_review(self, auto: bool = False) -> None:
        with self._lock:
            self._busy_check()
            if self.baseline is None:
                raise ValueError(self._t("no_task_yet"))
            # On a re-review the reviewer checks that its earlier notes were fixed.
            previous = self.verdict["issues"] if self.verdict and self.verdict.get("sent") else None
            self.agents["reviewer"]["status"] = "reviewing"
            self._phrase("reviewer", "looking_at_changes")
        if auto:
            self._log_entry("office", "auto", self._t("autopilot_review"))
        else:
            self._log_entry("user", "request", self._t("log_review_request"))
        self._emit_state()
        self._start(self._review, previous)

    def accept(self) -> None:
        with self._lock:
            self._busy_check()
            if self.baseline is None:
                raise ValueError(self._t("nothing_to_accept"))
            self.baseline = self._commit(f"office: accepted: {self.task_title or 'work'}")
            # Accepted work is done; the next task, or the next idea, starts from this commit.
            self.task = None
            self.task_title = None
            self.verdict = None
            self._phrase("worker", "accepted_waiting")
            self.agents["reviewer"]["status"] = "idle"
            self._phrase("reviewer", "reviewer_waiting")
        self._log_entry("user", "accept", self._t("log_accept", commit=self.baseline[:8]))
        self._emit_state()

    def stop(self, agent: str = "worker") -> None:
        with self._lock:
            run = self._ideator_run if agent == "ideator" else self._worker_run
        if run is None:
            raise ValueError(self._t("ideator_not_running" if agent == "ideator" else "worker_not_running"))
        run.stop()

    def generate_ideas(self, topic: str) -> None:
        topic = topic.strip()
        if not topic:
            raise ValueError(self._t("empty_topic"))
        with self._lock:
            # The idea maker only reads, so it may think while the others work.
            if self.agents["ideator"]["status"] == "thinking":
                raise Busy(self._t("busy_ideator"))
            self.agents["ideator"]["status"] = "thinking"
            self._phrase("ideator", "ideator_thinking", topic=_shorten(topic, 40))
        self._log_entry("user", "topic", self._t("log_topic", topic=topic))
        self._emit_state()
        self._start(self._ideate, topic)

    def hand_off(self, index) -> None:
        """Gives one of the ideas to the developer as its next task."""
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
            text = task_from_idea(idea, self.topic or "", self._t("idea_intro"), self._t("idea_guard"))
            self.start_task(text, title=idea["title"], from_idea=True)
            idea["handed"] = True
            self._phrase("ideator", "handed_off", title=_shorten(idea["title"], 40))
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
            # Pick up from wherever the work is now.
            self._autopilot_step()

    def _autopilot_step(self) -> None:
        """Takes the next step of the work -> review -> fixes loop, if the autopilot is on."""
        with self._lock:
            pilot = self.autopilot
            if not pilot["enabled"] or pilot["halted"] or self.task is None:
                return
            if self.agents["worker"]["status"] == "working" or self.agents["reviewer"]["status"] == "reviewing":
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
            else:
                pilot["round"] += 1
                action = "rework"
            rounds, limit = pilot["round"], pilot["max_rounds"]

        try:
            if action == "review":
                self.request_review(auto=True)
            elif action == "rework":
                self._log_entry("office", "auto", self._t("autopilot_round", round=rounds, max=limit))
                self.send_rework(auto=True)
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
            if not self.autopilot["enabled"] or not self.ideas or self.task is not None:
                return
            if self.agents["worker"]["status"] == "working" or self.agents["reviewer"]["status"] == "reviewing":
                return
            best = next((n for n, i in enumerate(self.ideas) if i["recommended"] and not i["handed"]), None)
            if best is None:
                return
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

    def _work(self, prompt: str) -> None:
        # The language goes in every message: a resumed session keeps its original system prompt.
        run = ClaudeCodeRun(
            f"{prompt}\n\n{self._t('reply_in')}",
            cwd=self.workspace,
            tools=self.worker_tools,
            append_system_prompt=WORKER_PROMPT,
            model=self.model,
            effort=self.effort,
            resume=self.session_id,
            accept_edits=True,
            plugin_dirs=self._plugin_dirs["worker"],
        )
        with self._lock:
            self._worker_run = run
        try:
            result = run.run(lambda e: self._on_agent_event("worker", e))
        except (ClaudeCodeError, OSError) as e:
            # Any failure must end in "idle": a stuck "working" would block the office for good.
            stopped = str(e) == "stopped"
            self._log_entry("worker", "error", self._t("log_stopped") if stopped else str(e))
            with self._lock:
                self.agents["worker"]["skill"] = None
            self._announce("worker", "stopped" if stopped else "went_wrong", "idle")
            self._halt_autopilot("stopped" if stopped else "error")
            return
        finally:
            with self._lock:
                self._worker_run = None

        with self._lock:
            self.session_id = result.session_id or self.session_id
            self.cost_usd += result.cost_usd or 0
            self.agents["worker"]["skill"] = None
        if result.text:
            self._log_entry("worker", "result", result.text)
        self._announce("worker", "done", "idle")
        self._autopilot_step()

    def _ideate(self, topic: str) -> None:
        run = ClaudeCodeRun(
            # Like the worker, the language goes in every message of the resumed conversation.
            idea_request(topic, self._t("reply_in")),
            cwd=self.workspace,
            tools=IDEATOR_TOOLS,
            system_prompt=IDEATOR_PROMPT,
            json_schema=IdeasOutput.model_json_schema(),
            model=self.model,
            effort=self.effort,
            resume=self._ideator_session,
            plugin_dirs=self._plugin_dirs["ideator"],
        )
        with self._lock:
            self._ideator_run = run
        try:
            result = run.run(lambda e: self._on_agent_event("ideator", e))
            ideas = parse_ideas(result.structured_output)
        except (ClaudeCodeError, IdeasError, OSError) as e:
            stopped = str(e) == "stopped"
            self._log_entry("ideator", "error", self._t("log_stopped") if stopped else str(e))
            with self._lock:
                self.agents["ideator"]["skill"] = None
            self._announce("ideator", "stopped" if stopped else "ideas_failed", "idle")
            return
        finally:
            with self._lock:
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

    def _review(self, previous: list[dict] | None = None) -> None:
        try:
            ctx = context.collect_diff(self.workspace, base=self.baseline)
            config = load_config(self.workspace)
            checks = config.get("checks", [])
            if checks and "Bash" not in self.worker_tools:
                # The developer can still edit .ai-review.toml, so without Bash its commands must not run either.
                self._log_entry("reviewer", "check", self._t("checks_skipped"))
                checks = []
            for command in checks:
                self._announce("reviewer", "running", command=command[:60])
                check = context.run_check(command, self.workspace)
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
                verdict = review(
                    ctx,
                    backend="claude-code",
                    model=self.model,
                    effort=self.effort or "high",
                    instructions=instructions,
                    cwd=self.workspace,
                    on_event=lambda e: self._on_agent_event("reviewer", e),
                    plugin_dirs=self._plugin_dirs["reviewer"],
                    previous=previous,
                )
                blocking = sum(1 for i in verdict.issues if i.severity in BLOCKING)
                if verdict.approved:
                    phrase = ("approved", {})
                else:
                    phrase = ("needs_fixes", {"count": blocking}) if blocking else ("checks_failed", {})
        except (context.ContextError, ConfigError, ReviewError, OSError) as e:
            # A stuck "reviewing" would block the office, so every expected failure ends the review.
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

    def _on_agent_event(self, agent: str, event: dict) -> None:
        if event.get("type") == "system" and event.get("subtype") == "init" and agent == "worker":
            with self._lock:
                self.session_id = event.get("session_id") or self.session_id
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
        """Waits until no agent thread is running, including ones the autopilot starts; for tests."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                alive = [thread for thread in self._threads if thread.is_alive()]
            if not alive:
                return
            alive[0].join(max(0.0, deadline - time.monotonic()))


def verdict_to_dict(verdict: Verdict, ctx: context.ReviewContext) -> dict:
    data = asdict(verdict)
    data["issues"] = [i.model_dump() for i in verdict.issues]
    data["checks"] = [{"command": c.command, "passed": c.passed} for c in ctx.checks]
    return data


def _shorten(text: str, limit: int = 90) -> str:
    first = next(iter(text.strip().splitlines()), "")
    return first if len(first) <= limit else first[: limit - 1] + "…"
