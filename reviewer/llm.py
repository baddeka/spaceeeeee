"""Asks Claude to review the collected context and decides the verdict."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from .context import ReviewContext

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "high"

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


class ReviewError(Exception):
    pass


def build_prompt(ctx: ReviewContext, instructions: str | None = None) -> str:
    parts = [f"# Scope\n{ctx.description}\n"]

    if instructions:
        parts.append(f"# Project-specific review instructions\n{instructions}\n")

    if ctx.checks:
        parts.append("# Check results")
        for check in ctx.checks:
            if check.timed_out:
                status = "TIMED OUT"
            else:
                status = "PASSED" if check.passed else f"FAILED (exit code {check.exit_code})"
            note = " (output truncated to its last part)" if check.truncated else ""
            parts.append(
                f"## `{check.command}`: {status}{note}\n```\n{check.output.strip()}\n```"
            )
        parts.append("")
    else:
        parts.append("# Check results\nNo checks were configured.\n")

    if ctx.diff:
        parts.append(f"# Diff\n```diff\n{ctx.diff}\n```\n")

    parts.append("# Files")
    for f in ctx.files:
        if f.content is None:
            parts.append(f"## {f.path}\n(not shown: {f.skipped_reason})")
        else:
            parts.append(f"## {f.path}\n```\n{f.content}\n```")

    return "\n".join(parts)


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
    client: anthropic.Anthropic | None = None,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    instructions: str | None = None,
) -> Verdict:
    if not ctx.diff and not ctx.files:
        raise ReviewError("nothing to review: no changes found")

    prompt = build_prompt(ctx, instructions)
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ReviewError(
            f"the change is too large to review in one request ({len(prompt):,} characters); "
            "narrow it with --base or --files"
        )

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
        raise ReviewError("no API credentials: set ANTHROPIC_API_KEY") from e

    if message.stop_reason == "refusal":
        raise ReviewError("the model declined to review this change")
    if message.stop_reason == "max_tokens":
        raise ReviewError("the review was cut off at the output limit")
    if message.parsed_output is None:
        raise ReviewError("the model returned no structured review")

    return decide(message.parsed_output, ctx, message.model)
