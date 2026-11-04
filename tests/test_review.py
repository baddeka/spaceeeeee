import json

import pytest

from reviewer import cli, llm
from reviewer.context import CheckResult, FileSnapshot, ReviewContext
from reviewer.llm import Issue, ReviewError, ReviewOutput

from .conftest import FakeClient


def make_issue(severity, title="problem"):
    return Issue(
        severity=severity, file="a.py", line=1, title=title, explanation="e", suggestion="s"
    )


def make_ctx(checks=()):
    return ReviewContext(
        description="test",
        diff="+x = 1\n",
        files=[FileSnapshot("a.py", "x = 1\n")],
        checks=list(checks),
    )


@pytest.mark.parametrize(
    "severities, approved",
    [([], True), (["minor", "nit"], True), (["major"], False), (["nit", "critical"], False)],
)
def test_blocking_severities_decide_the_verdict(severities, approved):
    output = ReviewOutput(summary="s", issues=[make_issue(s) for s in severities])

    verdict = llm.decide(output, make_ctx(), "m")

    assert verdict.approved is approved


def test_failing_check_blocks_approval_even_without_issues():
    ctx = make_ctx([CheckResult("pytest", 1, "1 failed")])

    verdict = llm.decide(ReviewOutput(summary="s", issues=[]), ctx, "m")

    assert not verdict.approved
    assert verdict.reasons == ["check failed: pytest"]


def test_issues_are_sorted_most_severe_first():
    output = ReviewOutput(
        summary="s", issues=[make_issue("nit"), make_issue("critical"), make_issue("minor")]
    )

    verdict = llm.decide(output, make_ctx(), "m")

    assert [i.severity for i in verdict.issues] == ["critical", "minor", "nit"]


def test_prompt_contains_checks_diff_and_files():
    ctx = make_ctx([CheckResult("pytest -q", 1, "FAILED test_x", truncated=True)])
    ctx.files.append(FileSnapshot("big.bin", None, "binary"))

    prompt = llm.build_prompt(ctx, instructions="We use tabs.")

    assert "`pytest -q`: FAILED (exit code 1) (output truncated" in prompt
    assert "FAILED test_x" in prompt
    assert "+x = 1" in prompt
    assert "(not shown: binary)" in prompt
    assert "We use tabs." in prompt


def test_review_sends_expected_request():
    client = FakeClient(parsed_output=ReviewOutput(summary="ok", issues=[]))

    verdict = llm.review(make_ctx(), client=client, effort="max")

    assert verdict.approved
    req = client.requests[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["output_config"] == {"effort": "max"}
    assert req["output_format"] is ReviewOutput
    assert req["fallbacks"] == "default"
    assert req["betas"] == ["server-side-fallback-2026-07-01"]


@pytest.mark.parametrize(
    "stop_reason, parsed, message",
    [
        ("refusal", None, "declined"),
        ("max_tokens", None, "cut off"),
        ("end_turn", None, "no structured review"),
    ],
)
def test_review_surfaces_unusable_responses(stop_reason, parsed, message):
    client = FakeClient(parsed_output=parsed, stop_reason=stop_reason)

    with pytest.raises(ReviewError, match=message):
        llm.review(make_ctx(), client=client)


def test_review_refuses_oversized_prompt(monkeypatch):
    monkeypatch.setattr(llm, "MAX_PROMPT_CHARS", 10)

    with pytest.raises(ReviewError, match="too large"):
        llm.review(make_ctx(), client=FakeClient())


def test_review_without_credentials(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", "/nonexistent")
    import anthropic

    with pytest.raises(ReviewError, match="no API credentials"):
        llm.review(make_ctx(), client=anthropic.Anthropic(max_retries=0))


def test_review_with_nothing_to_review():
    with pytest.raises(ReviewError, match="nothing to review"):
        llm.review(ReviewContext("empty", ""), client=FakeClient())


def test_cli_exit_codes_and_json(repo, capsys):
    (repo / "a.py").write_text("x = 1\n")
    (repo / ".ai-review.toml").write_text('checks = ["exit 1"]\neffort = "low"\n')
    client = FakeClient(parsed_output=ReviewOutput(summary="looks fine", issues=[]))

    code = cli.main(["--repo", str(repo), "--json"], client=client)

    out = json.loads(capsys.readouterr().out)
    assert code == cli.EXIT_CHANGES_REQUESTED
    assert out["approved"] is False
    assert out["checks"][0]["passed"] is False
    assert client.requests[0]["output_config"] == {"effort": "low"}


def test_cli_approves_clean_change(repo, capsys):
    (repo / "a.py").write_text("x = 1\n")
    client = FakeClient(parsed_output=ReviewOutput(summary="fine", issues=[make_issue("nit")]))

    code = cli.main(["--repo", str(repo), "--check", "true"], client=client)

    assert code == cli.EXIT_APPROVED
    assert "APPROVED" in capsys.readouterr().out


def test_cli_reports_errors_with_exit_code_2(repo, capsys):
    code = cli.main(["--repo", str(repo), "--files", "missing.py"], client=FakeClient())

    assert code == cli.EXIT_ERROR
    assert "not a file" in capsys.readouterr().err
