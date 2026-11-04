"""Collects what the reviewer looks at: the diff, changed files, and check results."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Git's well-known empty tree: diffing against it shows every file as added.
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

MAX_FILE_BYTES = 100_000
MAX_CHECK_OUTPUT_CHARS = 20_000


class ContextError(Exception):
    pass


@dataclass
class FileSnapshot:
    path: str
    content: str | None
    skipped_reason: str | None = None
    # A new file's every line is already in the diff, so its content need not be sent twice.
    is_new: bool = False


@dataclass
class CheckResult:
    command: str
    exit_code: int | None
    output: str
    timed_out: bool = False
    truncated: bool = False

    @property
    def passed(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


@dataclass
class ReviewContext:
    description: str
    diff: str
    files: list[FileSnapshot] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)


def run_git(repo: Path, *args: str) -> str:
    try:
        # Git prints file contents as they are, in any encoding, so undecodable bytes are replaced.
        proc = subprocess.run(
            ["git", *args], cwd=repo, capture_output=True, encoding="utf-8", errors="replace", check=False
        )
    except FileNotFoundError as e:
        raise ContextError("git is not installed") from e
    if proc.returncode != 0:
        raise ContextError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def _paths(repo: Path, *args: str) -> list[str]:
    """Paths printed by git with -z, which keeps non-ASCII names as they are instead of quoting them."""
    return [p for p in run_git(repo, *args, "-z").split("\0") if p]


def _has_head(repo: Path) -> bool:
    try:
        run_git(repo, "rev-parse", "--verify", "--quiet", "HEAD")
    except ContextError:
        return False
    return True


def _resolve_target(repo: Path, base: str | None) -> tuple[str, str]:
    """Returns (git ref to diff the working tree against, human description)."""
    if base:
        merge_base = run_git(repo, "merge-base", base, "HEAD").strip()
        return merge_base, f"changes since {base} (merge-base {merge_base[:10]})"
    if _has_head(repo):
        return "HEAD", "uncommitted changes against HEAD"
    return EMPTY_TREE, "all files (repository has no commits yet)"


def read_snapshot(repo: Path, rel_path: str) -> FileSnapshot:
    path = repo / rel_path
    if not path.is_file():
        return FileSnapshot(rel_path, None, "deleted")
    if path.stat().st_size > MAX_FILE_BYTES:
        return FileSnapshot(rel_path, None, f"larger than {MAX_FILE_BYTES} bytes")
    data = path.read_bytes()
    if b"\0" in data:
        return FileSnapshot(rel_path, None, "binary")
    try:
        return FileSnapshot(rel_path, data.decode("utf-8"))
    except UnicodeDecodeError:
        return FileSnapshot(rel_path, None, "not UTF-8")


def collect_diff(repo: Path, base: str | None = None) -> ReviewContext:
    target, description = _resolve_target(repo, base)
    diff = run_git(repo, "diff", target)
    changed = set(_paths(repo, "diff", "--name-only", target))
    added = set(_paths(repo, "diff", "--name-only", "--diff-filter=A", target))
    untracked = _paths(repo, "ls-files", "--others", "--exclude-standard")

    # Untracked files never show up in `git diff`, but they are part of the change.
    for rel_path in untracked:
        if rel_path not in changed:
            changed.add(rel_path)
            added.add(rel_path)
            diff += _untracked_as_diff(repo, rel_path)

    files = [read_snapshot(repo, p) for p in sorted(changed)]
    for snapshot in files:
        snapshot.is_new = snapshot.path in added
    return ReviewContext(description=description, diff=diff, files=files)


def _untracked_as_diff(repo: Path, rel_path: str) -> str:
    snapshot = read_snapshot(repo, rel_path)
    if snapshot.content is None:
        return f"\nnew file {rel_path} ({snapshot.skipped_reason}, content not shown)\n"
    lines = snapshot.content.splitlines()
    body = "".join(f"+{line}\n" for line in lines)
    return (
        f"diff --git a/{rel_path} b/{rel_path}\n"
        f"new file (untracked)\n--- /dev/null\n+++ b/{rel_path}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n{body}"
    )


def collect_files(repo: Path, paths: list[str]) -> ReviewContext:
    files = []
    root = repo.resolve()
    for p in paths:
        path = (repo / p).resolve()
        if not path.is_file():
            raise ContextError(f"not a file: {p}")
        if not path.is_relative_to(root):
            raise ContextError(f"outside the repository: {p}")
        files.append(read_snapshot(repo, path.relative_to(root).as_posix()))
    return ReviewContext(description=f"full review of {len(files)} file(s)", diff="", files=files)


def run_check(command: str, repo: Path, timeout: float = 600) -> CheckResult:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=repo,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        output = _decode(e.stdout) + _decode(e.stderr)
        return CheckResult(command, None, _tail(output)[0], timed_out=True)

    output, truncated = _tail(proc.stdout + proc.stderr)
    return CheckResult(command, proc.returncode, output, truncated=truncated)


def _decode(data: bytes | str | None) -> str:
    if data is None:
        return ""
    return data if isinstance(data, str) else data.decode("utf-8", "replace")


def _tail(output: str) -> tuple[str, bool]:
    # Failures are usually reported at the end, so keep the tail.
    if len(output) <= MAX_CHECK_OUTPUT_CHARS:
        return output, False
    return output[-MAX_CHECK_OUTPUT_CHARS:], True
