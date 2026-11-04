"""Runs Claude Code headless (`claude -p`), so a Claude subscription can be used instead of an API key."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")


class ClaudeCodeError(Exception):
    pass


@dataclass
class RunResult:
    session_id: str | None
    text: str
    structured_output: dict | None
    cost_usd: float | None
    model: str | None


class ClaudeCodeRun:
    """One `claude -p` process. Streams its events to `on_event` and returns the final result."""

    def __init__(
        self,
        prompt: str,
        *,
        cwd: Path,
        tools: list[str],
        system_prompt: str | None = None,
        append_system_prompt: str | None = None,
        json_schema: dict | None = None,
        model: str | None = None,
        effort: str | None = None,
        resume: str | None = None,
        accept_edits: bool = False,
        persist_session: bool = True,
        plugin_dirs: list[Path] | None = None,
        claude_bin: str | None = None,
    ):
        self.prompt = prompt
        self.cwd = cwd
        self.claude_bin = claude_bin or CLAUDE_BIN
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._stopped = False

        args = ["-p", "--output-format", "stream-json", "--verbose"]
        # --tools limits which built-in tools exist at all; "" disables every one.
        args += ["--tools", ",".join(tools)]
        if tools:
            args += ["--allowedTools", *tools]
        if system_prompt:
            args += ["--system-prompt", system_prompt]
        if append_system_prompt:
            args += ["--append-system-prompt", append_system_prompt]
        if json_schema:
            args += ["--json-schema", json.dumps(json_schema)]
        if model:
            args += ["--model", model]
        if effort:
            args += ["--effort", effort]
        if resume:
            args += ["--resume", resume]
        if accept_edits:
            args += ["--permission-mode", "acceptEdits"]
        if not persist_session:
            args.append("--no-session-persistence")
        # Plugins loaded this way exist for this run only, so each agent can get its own skills.
        for directory in plugin_dirs or []:
            args += ["--plugin-dir", str(directory)]
        self.args = args

    def run(self, on_event: Callable[[dict], None] | None = None) -> RunResult:
        binary = shutil.which(self.claude_bin)
        if binary is None:
            raise ClaudeCodeError(
                f"`{self.claude_bin}` not found: install Claude Code and sign in with `claude`"
            )
        with self._lock:
            if self._stopped:
                raise ClaudeCodeError("stopped")
            # stderr joins stdout so neither pipe can fill up while the other is read; its own
            # session lets stop() end the commands Claude Code started, not just Claude Code.
            self._proc = subprocess.Popen(
                [binary, *self.args],
                cwd=self.cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
        proc = self._proc
        assert proc.stdin and proc.stdout
        # The prompt goes through stdin so large diffs never hit argv limits. A thread writes it,
        # so a prompt bigger than the pipe buffer can't block while output waits to be read.
        writer = threading.Thread(target=_write_and_close, args=(proc.stdin, self.prompt), daemon=True)
        writer.start()

        result: dict | None = None
        other = deque(maxlen=5)  # the last lines that are not events, usually an error message
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                other.append(line)
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "result":
                result = event
            if on_event:
                on_event(event)

        returncode = proc.wait()
        writer.join()

        if self._stopped:
            raise ClaudeCodeError("stopped")
        if result is None:
            detail = other[-1] if other else f"exit code {returncode}"
            raise ClaudeCodeError(f"Claude Code exited without a result: {detail}")
        if result.get("is_error"):
            raise ClaudeCodeError(f"Claude Code error: {result.get('result') or result.get('subtype')}")

        models = list((result.get("modelUsage") or {}).keys())
        return RunResult(
            session_id=result.get("session_id"),
            text=result.get("result") or "",
            structured_output=result.get("structured_output"),
            cost_usd=result.get("total_cost_usd"),
            model=models[0] if models else None,
        )

    def stop(self) -> None:
        with self._lock:
            self._stopped = True
            if self._proc is None or self._proc.poll() is not None:
                return
            if not hasattr(os, "killpg"):  # Windows has no process groups
                self._proc.terminate()
                return
            try:
                os.killpg(self._proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


def _write_and_close(stream, text: str) -> None:
    try:
        stream.write(text)
        stream.close()
    except (BrokenPipeError, OSError):
        pass  # the process exited early; its output says why
