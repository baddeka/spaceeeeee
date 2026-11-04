"""The office: a worker agent that writes code and a reviewer agent that checks it on request."""

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
from reviewer.cli import load_config
from reviewer.llm import BLOCKING, ReviewError, Verdict, review

WORKER_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep", "Bash"]

WORKER_PROMPT = """\
You are the developer in a two-person office. You write code in the current directory.
A separate reviewer checks your work when the user asks; when you receive review findings, \
fix every critical and major issue, and the minor ones where the fix is clear.
Write all messages to the user in Russian. When you finish, say in two or three sentences \
what you did and how to run or test it.
"""

REVIEW_LANGUAGE = "Write the summary and every issue's title, explanation and suggestion in Russian."

LOG_LIMIT = 500


class Busy(Exception):
    pass


def describe_tool(name: str, args: dict) -> str:
    """A short, human description of what an agent is doing, shown in its speech bubble."""
    path = Path(str(args.get("file_path") or args.get("path") or "")).name
    if name == "Write":
        return f"Создаю {path}"
    if name in ("Edit", "MultiEdit"):
        return f"Правлю {path}"
    if name == "Read":
        return f"Читаю {path}"
    if name == "Bash":
        command = str(args.get("command", "")).strip().splitlines()[0] if args.get("command") else ""
        return f"Запускаю: {command[:60]}"
    if name == "Grep":
        return f"Ищу «{str(args.get('pattern', ''))[:40]}»"
    if name == "Glob":
        return "Смотрю файлы"
    if name == "TodoWrite":
        return "Планирую работу"
    if name == "StructuredOutput":
        # Claude Code delivers a --json-schema answer through this tool.
        return "Пишу заключение"
    return f"Использую {name}"


def rework_prompt(verdict: dict) -> str:
    if verdict["approved"]:
        lines = ["Ревьюер одобрил работу, но оставил замечания. Пользователь просит их учесть."]
    else:
        lines = ["Ревьюер проверил твою работу и вернул её на доработку."]
    if verdict["reasons"]:
        lines.append("Причины: " + "; ".join(verdict["reasons"]) + ".")
    lines.append("")
    for n, issue in enumerate(verdict["issues"], 1):
        where = f"{issue['file']}:{issue['line']}" if issue["line"] else issue["file"]
        lines.append(f"{n}. [{issue['severity'].upper()}] {where}: {issue['title']}")
        lines.append(f"   {issue['explanation']}")
        lines.append(f"   Как исправить: {issue['suggestion']}")
    lines.append("")
    lines.append("Исправь все critical и major, minor по возможности. Затем кратко напиши, что изменил.")
    return "\n".join(lines)


class Office:
    def __init__(
        self,
        workspace: Path,
        *,
        model: str | None = None,
        effort: str | None = None,
        worker_tools: list[str] | None = None,
    ):
        self.workspace = workspace
        self.model = model
        self.effort = effort
        self.worker_tools = worker_tools if worker_tools is not None else WORKER_TOOLS

        self._lock = threading.RLock()
        self._subscribers: list[queue.Queue] = []
        self._log: deque[dict] = deque(maxlen=LOG_LIMIT)
        self._worker_run: ClaudeCodeRun | None = None
        self._threads: list[threading.Thread] = []

        self.agents = {
            "worker": {"status": "idle", "bubble": "Жду задачу"},
            "reviewer": {"status": "idle", "bubble": "Позови, когда нужно проверить"},
        }
        self.session_id: str | None = None
        self.baseline: str | None = None
        self.task: str | None = None
        self.verdict: dict | None = None
        self.cost_usd = 0.0

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
                "has_session": self.session_id is not None,
            }

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
        self._emit_state()

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

    def _commit(self, message: str) -> str:
        self._git("add", "-A")
        self._git("commit", "-q", "--allow-empty", "-m", message)
        return self._git("rev-parse", "HEAD")

    # ----- actions -----

    def _busy_check(self, allow_reviewer: bool = False) -> None:
        if self.agents["worker"]["status"] == "working":
            raise Busy("Исполнитель ещё работает")
        if not allow_reviewer and self.agents["reviewer"]["status"] == "reviewing":
            raise Busy("Ревьюер ещё проверяет")

    def _start(self, target, *args) -> None:
        thread = threading.Thread(target=target, args=args, daemon=True)
        self._threads.append(thread)
        thread.start()

    def start_task(self, text: str) -> None:
        text = text.strip()
        if not text:
            raise ValueError("Пустая задача")
        with self._lock:
            self._busy_check()
            if self.baseline is None:
                # Everything after this commit is the worker's change, which is what gets reviewed.
                self.baseline = self._commit("office: before task")
            self.task = text
            self.verdict = None
            self.agents["worker"]["status"] = "working"
            self.agents["worker"]["bubble"] = "Читаю задачу"
            self.agents["reviewer"]["bubble"] = "Позови, когда нужно проверить"
        self._log_entry("user", "task", text)
        self._emit_state()
        self._start(self._work, text)

    def send_rework(self) -> None:
        with self._lock:
            self._busy_check()
            if not self.verdict or (self.verdict["approved"] and not self.verdict["issues"]):
                raise ValueError("Нет замечаний, которые нужно исправлять")
            if self.verdict.get("sent"):
                raise ValueError("Эти замечания уже отправлены. Позови ревьюера, чтобы проверить исправления")
            prompt = rework_prompt(self.verdict)
            # The verdict stays visible as the list being fixed, but it describes the old version now.
            self.verdict["sent"] = True
            self.agents["worker"]["status"] = "working"
            self.agents["worker"]["bubble"] = "Читаю замечания"
            self.agents["reviewer"]["status"] = "idle"
            self.agents["reviewer"]["bubble"] = "Жду исправлений"
        self._log_entry("reviewer", "handoff", "Отправил работу на доработку")
        self._emit_state()
        self._start(self._work, prompt)

    def request_review(self) -> None:
        with self._lock:
            self._busy_check()
            if self.baseline is None:
                raise ValueError("Сначала дай исполнителю задачу")
            self.agents["reviewer"]["status"] = "reviewing"
            self.agents["reviewer"]["bubble"] = "Смотрю, что изменилось"
        self._log_entry("user", "request", "Попросил ревьюера проверить работу")
        self._emit_state()
        self._start(self._review)

    def accept(self) -> None:
        with self._lock:
            self._busy_check()
            if self.baseline is None:
                raise ValueError("Принимать пока нечего")
            title = (self.task or "work").splitlines()[0][:60]
            self.baseline = self._commit(f"office: accepted: {title}")
            self.verdict = None
            self.agents["worker"]["bubble"] = "Работа принята. Жду новую задачу"
            self.agents["reviewer"]["bubble"] = "Позови, когда нужно проверить"
        self._log_entry("user", "accept", f"Принял работу (коммит {self.baseline[:8]})")
        self._emit_state()

    def stop(self) -> None:
        with self._lock:
            run = self._worker_run
        if run is None:
            raise ValueError("Исполнитель сейчас не работает")
        run.stop()

    # ----- agent loops -----

    def _work(self, prompt: str) -> None:
        run = ClaudeCodeRun(
            prompt,
            cwd=self.workspace,
            tools=self.worker_tools,
            append_system_prompt=WORKER_PROMPT,
            model=self.model,
            effort=self.effort,
            resume=self.session_id,
            accept_edits=True,
        )
        with self._lock:
            self._worker_run = run
        try:
            result = run.run(lambda e: self._on_agent_event("worker", e))
        except ClaudeCodeError as e:
            stopped = str(e) == "stopped"
            self._log_entry("worker", "error", "Остановлен" if stopped else str(e))
            self._set_agent("worker", "idle", "Остановился" if stopped else "Что-то пошло не так")
            return
        finally:
            with self._lock:
                self._worker_run = None

        with self._lock:
            self.session_id = result.session_id or self.session_id
            self.cost_usd += result.cost_usd or 0
        if result.text:
            self._log_entry("worker", "result", result.text)
        self._set_agent("worker", "idle", "Готово! Можно проверять")

    def _review(self) -> None:
        try:
            ctx = context.collect_diff(self.workspace, base=self.baseline)
            config = load_config(self.workspace)
            for command in config.get("checks", []):
                self._set_agent("reviewer", bubble=f"Запускаю: {command[:60]}")
                check = context.run_check(command, self.workspace)
                ctx.checks.append(check)
                self._log_entry(
                    "reviewer", "check", f"{'✓' if check.passed else '✗'} {command}"
                )
            self._set_agent("reviewer", bubble="Читаю изменения")
            instructions = "\n\n".join(filter(None, [config.get("instructions"), REVIEW_LANGUAGE]))
            verdict = review(
                ctx,
                backend="claude-code",
                model=self.model,
                effort=self.effort or "high",
                instructions=instructions,
                cwd=self.workspace,
                on_event=lambda e: self._on_agent_event("reviewer", e),
            )
        except (context.ContextError, ReviewError) as e:
            self._log_entry("reviewer", "error", str(e))
            self._set_agent("reviewer", "idle", "Не получилось проверить")
            return

        data = verdict_to_dict(verdict, ctx)
        with self._lock:
            self.verdict = data
        blocking = sum(1 for i in verdict.issues if i.severity in BLOCKING)
        if verdict.approved:
            bubble = "Одобрено! Можно принимать"
        else:
            bubble = f"Нужны правки (серьёзных: {blocking})" if blocking else "Не прошли проверки"
        self._log_entry("reviewer", "verdict", verdict.summary)
        self._set_agent("reviewer", "approved" if verdict.approved else "rejected", bubble)

    def _on_agent_event(self, agent: str, event: dict) -> None:
        if event.get("type") == "system" and event.get("subtype") == "init" and agent == "worker":
            with self._lock:
                self.session_id = event.get("session_id") or self.session_id
            return
        if event.get("type") != "assistant":
            return
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "tool_use":
                text = describe_tool(block.get("name", ""), block.get("input") or {})
                self._log_entry(agent, "tool", text)
                self._set_agent(agent, bubble=text)
            elif block.get("type") == "text" and block.get("text", "").strip():
                text = block["text"].strip()
                self._log_entry(agent, "say", text)
                self._set_agent(agent, bubble=_shorten(text))

    def wait_idle(self, timeout: float = 10) -> None:
        """Waits for background agent threads; used by tests."""
        for thread in list(self._threads):
            thread.join(timeout)


def verdict_to_dict(verdict: Verdict, ctx: context.ReviewContext) -> dict:
    data = asdict(verdict)
    data["issues"] = [i.model_dump() for i in verdict.issues]
    data["checks"] = [{"command": c.command, "passed": c.passed} for c in ctx.checks]
    return data


def _shorten(text: str, limit: int = 90) -> str:
    first = text.splitlines()[0]
    return first if len(first) <= limit else first[: limit - 1] + "…"
