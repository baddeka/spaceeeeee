"""Command line entry point: `ai-review` or `python -m reviewer`."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from dataclasses import asdict
from pathlib import Path

from . import context
from .llm import DEFAULT_EFFORT, DEFAULT_MODEL, ReviewError, Verdict, review

CONFIG_FILE = ".ai-review.toml"

EXIT_APPROVED = 0
EXIT_CHANGES_REQUESTED = 1
EXIT_ERROR = 2

SEVERITY_COLORS = {"critical": "31;1", "major": "31", "minor": "33", "nit": "36"}


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="ai-review",
        description="Review code changes with Claude, grounded in your tests and linters.",
    )
    scope = p.add_mutually_exclusive_group()
    scope.add_argument("--base", help="review everything since this branch or commit, e.g. main")
    scope.add_argument("--files", nargs="+", help="review these files in full instead of a diff")
    p.add_argument(
        "--check",
        action="append",
        default=[],
        metavar="CMD",
        help="command to run before the review, e.g. 'pytest -q' (repeatable)",
    )
    p.add_argument("--no-checks", action="store_true", help=f"skip checks from {CONFIG_FILE}")
    p.add_argument("--repo", default=".", help="repository root (default: current directory)")
    p.add_argument(
        "--backend",
        choices=["claude-code", "api"],
        help="claude-code uses your Claude subscription through `claude -p`; "
        "api uses ANTHROPIC_API_KEY (default: claude-code)",
    )
    p.add_argument(
        "--model",
        help=f"Claude model (default: {DEFAULT_MODEL} for api, Claude Code's default for claude-code)",
    )
    p.add_argument(
        "--effort",
        choices=["low", "medium", "high", "xhigh", "max"],
        help=f"how hard the model thinks (default: {DEFAULT_EFFORT})",
    )
    p.add_argument("--json", action="store_true", help="print the verdict as JSON")
    return p.parse_args(argv)


def load_config(repo: Path) -> dict:
    path = repo / CONFIG_FILE
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def format_verdict(verdict: Verdict, ctx: context.ReviewContext, color: bool) -> str:
    def c(code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if color else text

    lines = [c("1", f"Scope: {ctx.description}")]
    for check in ctx.checks:
        mark = c("32", "PASS") if check.passed else c("31", "FAIL")
        lines.append(f"  [{mark}] {check.command}")
    lines.append("")
    lines.append(verdict.summary)
    lines.append("")

    for issue in verdict.issues:
        where = f"{issue.file}:{issue.line}" if issue.line else issue.file
        tag = c(SEVERITY_COLORS[issue.severity], issue.severity.upper())
        lines.append(f"{tag} {where}: {issue.title}")
        lines.append(f"    {issue.explanation}")
        lines.append(f"    Fix: {issue.suggestion}")
        lines.append("")

    if verdict.approved:
        lines.append(c("32;1", "APPROVED"))
    else:
        lines.append(c("31;1", "CHANGES REQUESTED") + f" ({'; '.join(verdict.reasons)})")
    return "\n".join(lines)


def main(argv: list[str] | None = None, client=None) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).resolve()

    try:
        config = load_config(repo)
        if args.files:
            ctx = context.collect_files(repo, args.files)
        else:
            ctx = context.collect_diff(repo, args.base)

        checks = args.check + ([] if args.no_checks else config.get("checks", []))
        for command in checks:
            print(f"running: {command}", file=sys.stderr)
            ctx.checks.append(context.run_check(command, repo))

        print("reviewing...", file=sys.stderr)
        verdict = review(
            ctx,
            backend=args.backend or config.get("backend", "claude-code"),
            client=client,
            model=args.model or config.get("model"),
            effort=args.effort or config.get("effort", DEFAULT_EFFORT),
            instructions=config.get("instructions"),
            cwd=repo,
        )
    except (context.ContextError, ReviewError, tomllib.TOMLDecodeError) as e:
        print(f"ai-review: error: {e}", file=sys.stderr)
        return EXIT_ERROR

    if args.json:
        out = asdict(verdict) | {"checks": [asdict(ch) | {"passed": ch.passed} for ch in ctx.checks]}
        out["issues"] = [i.model_dump() for i in verdict.issues]
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(format_verdict(verdict, ctx, color=sys.stdout.isatty()))

    return EXIT_APPROVED if verdict.approved else EXIT_CHANGES_REQUESTED


if __name__ == "__main__":
    sys.exit(main())
