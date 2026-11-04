"""Runs Claude Code headless (`claude -p`), so a Claude subscription can be used instead of an API key."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
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
    raw: dict = field(default_factory=dict)


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
        claude_bin: str | None = None,
    ):
        self.prompt = prompt
        self.cwd = cwd
        self.claude_bin = claude_bin or CLAUDE_BIN
        self._proc: subprocess.Popen | None = None
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
        self.args = args

    def run(self, on_event: Callable[[dict], None] | None = None) -> RunResult:
        if shutil.which(self.claude_bin) is None:
            raise ClaudeCodeError(
                f"`{self.claude_bin}` not found: install Claude Code and sign in with `claude`"
            )
        self._proc = subprocess.Popen(
            [self.claude_bin, *self.args],
            cwd=self.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # The prompt goes through stdin so large diffs never hit argv limits.
        assert self._proc.stdin and self._proc.stdout and self._proc.stderr
        try:
            self._proc.stdin.write(self.prompt)
            self._proc.stdin.close()
        except BrokenPipeError:
            pass

        result: dict | None = None
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "result":
                result = event
            if on_event:
                on_event(event)

        stderr = self._proc.stderr.read()
        returncode = self._proc.wait()

        if self._stopped:
            raise ClaudeCodeError("stopped")
        if result is None:
            detail = stderr.strip().splitlines()[-1] if stderr.strip() else f"exit code {returncode}"
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
            raw=result,
        )

    def stop(self) -> None:
        self._stopped = True
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
