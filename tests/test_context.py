import os
import signal
import subprocess
import time

import pytest

from reviewer import context
from reviewer.context import EMPTY_TREE

from .conftest import git, process_gone, wait_for_file


def test_repo_without_commits_reviews_every_file(repo):
    (repo / "app.py").write_text("print('hi')\n")

    ctx = context.collect_diff(repo)

    assert "no commits" in ctx.description
    assert [f.path for f in ctx.files] == ["app.py"]
    assert "+print('hi')" in ctx.diff


def test_diff_against_head_includes_modified_and_untracked(repo):
    (repo / "a.py").write_text("x = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    (repo / "a.py").write_text("x = 2\n")
    (repo / "b.py").write_text("y = 3\n")

    ctx = context.collect_diff(repo)

    assert ctx.description == "uncommitted changes against HEAD"
    assert [f.path for f in ctx.files] == ["a.py", "b.py"]
    assert "-x = 1" in ctx.diff and "+x = 2" in ctx.diff
    assert "+y = 3" in ctx.diff


def test_base_diff_uses_merge_base(repo):
    (repo / "a.py").write_text("x = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    git(repo, "checkout", "-qb", "feature")
    (repo / "a.py").write_text("x = 2\n")
    git(repo, "commit", "-qam", "change")

    ctx = context.collect_diff(repo, base="main")

    assert ctx.description.startswith("changes since main")
    assert "+x = 2" in ctx.diff


def test_deleted_and_binary_files_are_marked_not_shown(repo):
    (repo / "gone.py").write_text("x = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    (repo / "gone.py").unlink()
    (repo / "logo.png").write_bytes(b"\x89PNG\0\0data")

    files = {f.path: f for f in context.collect_diff(repo).files}

    assert files["gone.py"].skipped_reason == "deleted"
    assert files["logo.png"].skipped_reason == "binary"


def test_collect_files_rejects_missing_path(repo):
    try:
        context.collect_files(repo, ["nope.py"])
    except context.ContextError as e:
        assert "nope.py" in str(e)
    else:
        raise AssertionError("expected ContextError")


def test_run_check_reports_pass_and_fail(repo):
    ok = context.run_check("echo fine", repo)
    bad = context.run_check("echo broken >&2; exit 3", repo)

    assert ok.passed and "fine" in ok.output
    assert not bad.passed and bad.exit_code == 3 and "broken" in bad.output


def test_run_check_timeout_is_a_failure(repo):
    result = context.run_check("sleep 5", repo, timeout=0.2)

    assert result.timed_out and not result.passed


def test_long_check_output_keeps_the_tail(repo):
    result = context.run_check(
        f"python3 -c \"print('a' * {context.MAX_CHECK_OUTPUT_CHARS}); print('THE END')\"", repo
    )

    assert result.truncated
    assert result.output.rstrip().endswith("THE END")


def test_empty_tree_constant_matches_git(repo):
    out = context.run_git(repo, "hash-object", "-t", "tree", "/dev/null")
    assert out.strip() == EMPTY_TREE


def test_non_ascii_paths_are_read_not_marked_deleted(repo):
    (repo / "a.py").write_text("x = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    (repo / "заметки.md").write_text("привет\n")
    (repo / "файл с пробелом.py").write_text("y = 2\n")
    git(repo, "add", "файл с пробелом.py")

    ctx = context.collect_diff(repo)

    files = {f.path: f for f in ctx.files}
    assert set(files) == {"заметки.md", "файл с пробелом.py"}
    assert files["заметки.md"].content == "привет\n" and files["заметки.md"].is_new
    assert files["файл с пробелом.py"].skipped_reason is None


def test_files_in_other_encodings_do_not_break_the_diff(repo):
    (repo / "old.txt").write_text("a\n")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    (repo / "old.txt").write_bytes("Привет\n".encode("cp1251"))

    ctx = context.collect_diff(repo)

    assert "old.txt" in ctx.diff
    assert ctx.files[0].skipped_reason == "not UTF-8"


def test_check_output_in_other_encodings_is_kept(repo):
    result = context.run_check("printf '\\377ok'", repo)

    assert result.passed and result.output.endswith("ok")


def test_collect_files_rejects_paths_outside_the_repo(repo, tmp_path_factory):
    outside = tmp_path_factory.mktemp("elsewhere") / "secret.txt"
    outside.write_text("x\n")

    with pytest.raises(context.ContextError, match="outside the repository"):
        context.collect_files(repo, [str(outside)])


def test_a_timed_out_check_ends_what_it_started(repo):
    pid_file = repo / "child.pid"

    result = context.run_check(f"sleep 30 & echo $! > {pid_file}; sleep 30", repo, timeout=1)

    assert result.timed_out
    assert process_gone(int(pid_file.read_text()))


def test_a_missing_folder_is_not_reported_as_missing_git(tmp_path):
    with pytest.raises(context.ContextError, match="not a folder"):
        context.collect_diff(tmp_path / "typo")


def test_a_check_that_detaches_a_child_does_not_hang_the_review(repo, monkeypatch):
    # The child leaves the check's session but keeps its output pipe open.
    monkeypatch.setattr(context, "KILLED_OUTPUT_SECONDS", 0.5)
    pid_file = repo / "detached.pid"
    detach = "python3 -c 'import os, time; os.setsid(); time.sleep(30)'"
    started = time.monotonic()

    result = context.run_check(f"echo before; {detach} & echo $! > {pid_file}; sleep 30", repo, timeout=1)

    try:
        assert result.timed_out
        assert time.monotonic() - started < 10
        assert "before" in result.output
    finally:
        os.kill(int(pid_file.read_text()), signal.SIGKILL)


def test_an_interrupted_check_ends_what_it_started(repo, monkeypatch):
    pid_file = repo / "child.pid"

    def interrupted(self, *args, **kwargs):
        wait_for_file(pid_file)
        raise KeyboardInterrupt  # Ctrl+C, which never reaches a command in its own session

    monkeypatch.setattr(subprocess.Popen, "communicate", interrupted)
    with pytest.raises(KeyboardInterrupt):
        context.run_check(f"sleep 30 & echo $! > {pid_file}; wait", repo)

    assert process_gone(int(pid_file.read_text()))
