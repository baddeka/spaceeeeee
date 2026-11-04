from reviewer import context
from reviewer.context import EMPTY_TREE

from .conftest import git


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
    out = context._git(repo, "hash-object", "-t", "tree", "/dev/null")
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
