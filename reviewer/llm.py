"""Asks Claude to review the collected context and decides the verdict."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import anthropic
from pydantic import BaseModel, Field, ValidationError

from .claude_code import ClaudeCodeError, ClaudeCodeRun
from .context import ReviewContext

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "high"
EFFORTS = ("low", "medium", "high", "xhigh", "max")

# Severities that block approval. The model rates each issue; the code decides.
BLOCKING = {"critical", "major"}

# Keeps the request comfortably inside the 1M-token context window.
MAX_PROMPT_CHARS = 2_500_000

SYSTEM_PROMPT = """\
You are a senior code reviewer. You review a change and report every real defect you find.

What counts as a defect: wrong behavior, crashes, unhandled edge cases, security holes, \
data loss, race conditions, broken contracts between components, missing error handling \
that a real input can reach, and tests that do not test what they claim.

How to rate severity:
- critical: security vulnerability, data loss, or the change breaks core functionality.
- major: a bug a real user or caller will hit, or a failing check caused by this change.
- minor: a real but low-impact problem, such as an unlikely edge case.
- nit: style, naming, or readability with no behavioral effect.

Rules:
- Check results are facts. A failing check caused by the change is at least a major issue. \
Do not claim the code works when a check says otherwise.
- For each issue, name the file and line (0 when it does not apply), explain the concrete \
input or path that triggers it, and suggest a fix.
- Report every issue you find with an honest severity; do not hold back minor ones and do \
not inflate nits. An empty issue list is correct when the change is sound.
- Review only the change and its direct effects, not unrelated pre-existing code.
"""


# With Claude Code the reviewer can open other files (callers, tests) but never edit them.
READ_ONLY_TOOLS = ["Read", "Grep", "Glob"]

CLAUDE_CODE_ADDENDUM = """
You are running inside the repository. When the diff alone is not enough, use Read, Grep \
and Glob to look at callers, definitions and tests. Never try to modify files.
"""


class Issue(BaseModel):
    severity: Literal["critical", "major", "minor", "nit"]
    file: str
    line: int = Field(description="1-based line number, or 0 if not applicable")
    title: str
    explanation: str = Field(description="What goes wrong and on which input or path")
    suggestion: str


class ReviewOutput(BaseModel):
    summary: str = Field(description="Two or three sentences on the change and its state")
    issues: list[Issue]


@dataclass
class Verdict:
    approved: bool
    summary: str
    issues: list[Issue]
    model: str
    reasons: list[str]
    cost_usd: float | None = None


class ReviewError(Exception):
    pass


def build_prompt(
    ctx: ReviewContext,
    instructions: str | None = None,
    previous: list[dict] | None = None,
    developer_reply: str | None = None,
) -> str:
    parts = [f"# Scope\n{ctx.description}\n"]

    if instructions:
        parts.append(f"# Project-specific review instructions\n{instructions}\n")

    if previous:
        parts.append(
            "# Notes from the previous review\n"
            "The developer was asked to fix these. Decide for each whether it is fixed, partly fixed, "
            "or not fixed, and report every one that is not fully fixed again."
        )
        for n, issue in enumerate(previous, 1):
            where = f"{issue['file']}:{issue['line']}" if issue.get("line") else issue.get("file", "")
            parts.append(f"{n}. [{issue['severity']}] {where} {issue['title']}: {issue['explanation']}")
        parts.append("")

    if developer_reply:
        parts.append(
            "# The developer's reply\n"
            "The developer's own account of what it changed, and why it left some notes as they are. "
            "Check it against the code; accept an explanation only when the code bears it out.\n"
            f"{_fenced(developer_reply)}\n"
        )

    if ctx.checks:
        parts.append("# Check results")
        for check in ctx.checks:
            if check.timed_out:
                status = "TIMED OUT"
            else:
                status = "PASSED" if check.passed else f"FAILED (exit code {check.exit_code})"
            note = " (output truncated to its last part)" if check.truncated else ""
            parts.append(f"## `{check.command}`: {status}{note}\n{_fenced(check.output.strip())}")
        parts.append("")
    else:
        parts.append("# Check results\nNo checks were configured.\n")

    if ctx.diff:
        parts.append(f"# Diff\n{_fenced(ctx.diff, 'diff')}\n")

    parts.append("# Files")
    for f in ctx.files:
        if f.content is None:
            parts.append(f"## {f.path}\n(not shown: {f.skipped_reason})")
        elif f.is_new and ctx.diff:
            parts.append(f"## {f.path}\n(new file: every line is in the diff above)")
        else:
            parts.append(f"## {f.path}\n{_fenced(f.content)}")

    return "\n".join(parts)


def _fenced(text: str, info: str = "") -> str:
    """A code block whose fence is longer than any backtick run in `text`.

    The developer writes the reply, the files and what the checks print, so none of them can
    close the block early and pass their own headings off as this prompt's sections.
    """
    fence = "```"
    while fence in text:
        fence += "`"
    return f"{fence}{info}\n{text}\n{fence}"


def decide(output: ReviewOutput, ctx: ReviewContext, model: str) -> Verdict:
    reasons = []
    for check in ctx.checks:
        if not check.passed:
            reasons.append(f"check failed: {check.command}")
    blocking = [i for i in output.issues if i.severity in BLOCKING]
    if blocking:
        reasons.append(f"{len(blocking)} blocking issue(s)")
    return Verdict(
        approved=not reasons,
        summary=output.summary,
        issues=sorted(output.issues, key=lambda i: ["critical", "major", "minor", "nit"].index(i.severity)),
        model=model,
        reasons=reasons,
    )


def review(
    ctx: ReviewContext,
    *,
    backend: str = "api",
    client: anthropic.Anthropic | None = None,
    model: str | None = None,
    effort: str = DEFAULT_EFFORT,
    instructions: str | None = None,
    cwd: Path | None = None,
    on_event: Callable[[dict], None] | None = None,
    plugin_dirs: list[Path] | None = None,
    previous: list[dict] | None = None,
    developer_reply: str | None = None,
    on_run: Callable[[ClaudeCodeRun], None] | None = None,
) -> Verdict:
    """Reviews through the Claude API (`backend="api"`) or Claude Code (`"claude-code"`).

    `plugin_dirs` gives a Claude Code reviewer extra skills; `previous` lists the notes of the
    last review so a re-review checks they were fixed, and `developer_reply` is what the
    developer said about them. `on_run` receives the Claude Code run before it starts, so it
    can be stopped.
    """
    if not ctx.diff and not ctx.files:
        raise ReviewError("nothing to review: no changes found")

    prompt = build_prompt(ctx, instructions, previous, developer_reply)
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ReviewError(
            f"the change is too large to review in one request ({len(prompt):,} characters); "
            "narrow it with --base or --files"
        )

    cost = None
    if backend == "claude-code":
        output, served_by, cost = _review_with_claude_code(
            prompt, model, effort, cwd, on_event, plugin_dirs, on_run
        )
    elif backend == "api":
        output, served_by = _review_with_api(prompt, client, model or DEFAULT_MODEL, effort)
    else:
        raise ReviewError(f"unknown backend: {backend}")
    verdict = decide(output, ctx, served_by)
    verdict.cost_usd = cost
    return verdict


def _review_with_api(
    prompt: str, client: anthropic.Anthropic | None, model: str, effort: str
) -> tuple[ReviewOutput, str]:
    client = client or anthropic.Anthropic()
    try:
        with client.beta.messages.stream(
            model=model,
            max_tokens=64000,
            system=SYSTEM_PROMPT,
            thinking={"type": "adaptive"},
            output_config={"effort": effort},
            output_format=ReviewOutput,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            message = stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise ReviewError("authentication failed: set ANTHROPIC_API_KEY") from e
    except anthropic.RateLimitError as e:
        raise ReviewError("rate limited by the API, try again later") from e
    except anthropic.APIStatusError as e:
        raise ReviewError(f"API error: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise ReviewError("could not reach the Anthropic API") from e
    except TypeError as e:
        # The SDK raises TypeError before sending when no credentials are configured.
        if "authentication method" not in str(e):
            raise
        raise ReviewError(
            "no API credentials: set ANTHROPIC_API_KEY or use --backend claude-code"
        ) from e

    if message.stop_reason == "refusal":
        raise ReviewError("the model declined to review this change")
    if message.stop_reason == "max_tokens":
        raise ReviewError("the review was cut off at the output limit")
    if message.parsed_output is None:
        raise ReviewError("the model returned no structured review")
    return message.parsed_output, message.model


def _review_with_claude_code(
    prompt: str,
    model: str | None,
    effort: str,
    cwd: Path | None,
    on_event: Callable[[dict], None] | None,
    plugin_dirs: list[Path] | None,
    on_run: Callable[[ClaudeCodeRun], None] | None = None,
) -> tuple[ReviewOutput, str, float | None]:
    run = ClaudeCodeRun(
        prompt,
        cwd=cwd or Path.cwd(),
        # Skills only add instructions, so the reviewer stays read-only with them.
        tools=READ_ONLY_TOOLS + (["Skill"] if plugin_dirs else []),
        system_prompt=SYSTEM_PROMPT + CLAUDE_CODE_ADDENDUM,
        json_schema=ReviewOutput.model_json_schema(),
        model=model,
        effort=effort,
        persist_session=False,
        plugin_dirs=plugin_dirs,
    )
    if on_run:
        on_run(run)
    try:
        result = run.run(on_event)
    except ClaudeCodeError as e:
        raise ReviewError(str(e)) from e
    if result.structured_output is None:
        raise ReviewError("Claude Code returned no structured review")
    try:
        output = ReviewOutput.model_validate(result.structured_output)
    except ValidationError as e:
        raise ReviewError(f"Claude Code returned a malformed review: {e}") from e
    return output, result.model or "claude-code", result.cost_usd
