import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from office.agents import Busy, Office, describe_tool, rework_prompt
from office.server import make_handler
from reviewer import claude_code, llm
from reviewer.claude_code import ClaudeCodeRun

FAKE = Path(__file__).parent / "fake_claude.py"


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    """Points the code at the fake CLI and returns a function that reads its calls."""
    launcher = tmp_path / "claude"
    launcher.write_text(f"#!/bin/sh\nexec {sys.executable} {FAKE} \"$@\"\n")
    launcher.chmod(0o755)
    log = tmp_path / "calls.jsonl"
    monkeypatch.setattr(claude_code, "CLAUDE_BIN", str(launcher))
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))

    def calls():
        if not log.exists():
            return []
        return [json.loads(line) for line in log.read_text().splitlines()]

    return calls


def make_office(tmp_path):
    return Office(tmp_path / "ws", lang="ru")


def test_claude_code_run_streams_events_and_returns_result(fake_claude, tmp_path):
    events = []
    result = ClaudeCodeRun("do it", cwd=tmp_path, tools=["Read", "Write"]).run(events.append)

    assert result.session_id == "sess-1"
    assert result.text == "Done: app.py prints hello. Run it with python3 app.py."
    assert result.model == "claude-test"
    assert [e["type"] for e in events] == ["system", "assistant", "result"]
    call = fake_claude()[0]
    assert call["prompt"] == "do it"
    assert call["args"][call["args"].index("--tools") + 1] == "Read,Write"


def test_claude_code_run_reports_crash(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_FAIL", "1")

    with pytest.raises(claude_code.ClaudeCodeError, match="boom"):
        ClaudeCodeRun("x", cwd=tmp_path, tools=[]).run()


def test_claude_code_missing_binary(tmp_path, monkeypatch):
    monkeypatch.setattr(claude_code, "CLAUDE_BIN", "definitely-not-installed-claude")

    with pytest.raises(claude_code.ClaudeCodeError, match="not found"):
        ClaudeCodeRun("x", cwd=tmp_path, tools=[]).run()


def test_review_backend_claude_code_is_read_only(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv(
        "FAKE_CLAUDE_REVIEW",
        json.dumps({"summary": "bad", "issues": [{
            "severity": "major", "file": "a.py", "line": 3, "title": "t",
            "explanation": "e", "suggestion": "s"}]}),
    )
    ctx = llm.ReviewContext("t", "+x\n")

    verdict = llm.review(ctx, backend="claude-code", cwd=tmp_path)

    assert not verdict.approved
    assert verdict.model == "claude-test"
    args = fake_claude()[0]["args"]
    assert args[args.index("--tools") + 1] == "Read,Grep,Glob"
    assert "--no-session-persistence" in args


def test_review_backend_rejects_malformed_output(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", json.dumps({"summary": "x"}))

    with pytest.raises(llm.ReviewError, match="malformed"):
        llm.review(llm.ReviewContext("t", "+x\n"), backend="claude-code", cwd=tmp_path)


def test_full_office_cycle(fake_claude, tmp_path, monkeypatch):
    office = make_office(tmp_path)

    office.start_task("Сделай hello world")
    office.wait_idle()
    state = office.snapshot()
    assert state["agents"]["worker"]["status"] == "idle"
    assert state["agents"]["worker"]["bubble"] == "Готово! Можно проверять"
    assert (tmp_path / "ws" / "app.py").exists()
    assert office.session_id == "sess-1"

    monkeypatch.setenv(
        "FAKE_CLAUDE_REVIEW",
        json.dumps({"summary": "плохо", "issues": [{
            "severity": "critical", "file": "app.py", "line": 1, "title": "Баг",
            "explanation": "ломается", "suggestion": "починить"}]}),
    )
    office.request_review()
    office.wait_idle()
    assert office.agents["reviewer"]["status"] == "rejected"
    assert office.verdict["approved"] is False
    review_call = fake_claude()[1]
    assert "+print('hello')" in review_call["prompt"]
    assert "Russian" in review_call["prompt"]

    office.send_rework()
    office.wait_idle()
    rework_call = fake_claude()[2]
    assert "Баг" in rework_call["prompt"]
    # The worker continues the same conversation, so it remembers the task.
    assert rework_call["args"][rework_call["args"].index("--resume") + 1] == "sess-1"
    assert office.agents["reviewer"]["status"] == "idle"
    with pytest.raises(ValueError, match="уже отправлены"):
        office.send_rework()

    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", json.dumps({"summary": "ок", "issues": []}))
    office.request_review()
    office.wait_idle()
    assert office.verdict["approved"] is True

    office.accept()
    log = office._git("log", "--format=%s")
    assert "office: accepted: Сделай hello world" in log
    assert office.verdict is None


def test_review_runs_project_checks(fake_claude, tmp_path):
    office = make_office(tmp_path)
    (tmp_path / "ws" / ".ai-review.toml").write_text('checks = ["exit 1"]\n')
    office.start_task("x")
    office.wait_idle()

    office.request_review()
    office.wait_idle()

    assert office.verdict["approved"] is False
    assert office.verdict["checks"] == [{"command": "exit 1", "passed": False}]


def test_busy_rules(tmp_path):
    office = make_office(tmp_path)
    with pytest.raises(ValueError):
        office.request_review()
    with pytest.raises(ValueError):
        office.send_rework()
    with pytest.raises(ValueError):
        office.start_task("   ")

    office.agents["worker"]["status"] = "working"
    with pytest.raises(Busy):
        office.start_task("again")


def test_worker_error_is_reported(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_FAIL", "1")
    office = make_office(tmp_path)

    office.start_task("x")
    office.wait_idle()

    assert office.agents["worker"]["status"] == "idle"
    assert office.agents["worker"]["bubble"] == "Что-то пошло не так"
    assert any(e["kind"] == "error" for e in office._log)


def test_describe_tool():
    assert describe_tool("Write", {"file_path": "/a/b/app.py"}) == "Creating app.py"
    assert describe_tool("Write", {"file_path": "/a/b/app.py"}, "ru") == "Создаю app.py"
    assert describe_tool("Bash", {"command": "pytest -q\nmore"}, "ru") == "Запускаю: pytest -q"
    assert describe_tool("Mystery", {}) == "Using Mystery"


def test_english_office_talks_to_agents_in_english(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    assert office.snapshot()["lang"] == "en"
    assert office.agents["worker"]["bubble"] == "Waiting for a task"

    office.start_task("Make hello world")
    office.wait_idle()
    office.request_review()
    office.wait_idle()

    worker_call, review_call = fake_claude()
    assert worker_call["prompt"].endswith("Reply in English.")
    assert "in English." in review_call["prompt"]
    assert office.agents["worker"]["bubble"] == "Done! Ready for review"


def test_switching_language_translates_fixed_bubbles(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    office._set_agent("reviewer", bubble="Reading app.py live from the model")

    office.set_language("ru")

    assert office.agents["worker"]["bubble"] == "Жду задачу"
    # Text an agent produced stays as it was written.
    assert office.agents["reviewer"]["bubble"] == "Reading app.py live from the model"
    office.start_task("x")
    office.wait_idle()
    assert fake_claude()[-1]["prompt"].endswith("Отвечай по-русски.")
    with pytest.raises(ValueError):
        office.set_language("de")


def test_unknown_language_is_rejected_at_start(tmp_path):
    with pytest.raises(ValueError):
        Office(tmp_path / "ws", lang="de")


def test_rework_allowed_for_approved_verdict_with_minor_issues(fake_claude, tmp_path):
    office = make_office(tmp_path)
    office.start_task("x")
    office.wait_idle()
    office.verdict = {"approved": True, "reasons": [], "issues": [{
        "severity": "minor", "file": "a.py", "line": 1, "title": "T",
        "explanation": "E", "suggestion": "S"}]}

    office.send_rework()
    office.wait_idle()

    assert "checkren одобряет работу, но есть замечания" in fake_claude()[-1]["prompt"]


def test_rework_prompt_lists_issues():
    text = rework_prompt({
        "approved": False,
        "reasons": ["check failed: pytest"],
        "issues": [{"severity": "major", "file": "a.py", "line": 0, "title": "T",
                    "explanation": "E", "suggestion": "S"}],
    })
    assert "check failed: pytest" in text
    assert "1. [MAJOR] a.py: T" in text


# ---------- HTTP ----------


@pytest.fixture
def server(tmp_path):
    office = make_office(tmp_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(office))
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}", office
    httpd.shutdown()


def request(url, method="GET", body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status, res.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_http_serves_page_and_state(server):
    base, _ = server
    status, html = request(base + "/")
    assert status == 200 and "AI Office" in html
    status, body = request(base + "/static/app.js")
    assert status == 200
    status, body = request(base + "/api/state")
    assert json.loads(body)["agents"]["worker"]["status"] == "idle"
    assert request(base + "/static/../agents.py")[0] == 404
    with urllib.request.urlopen(base + "/static/parens.woff2", timeout=5) as res:
        assert res.headers["Content-Type"] == "font/woff2"
        assert res.read(4) == b"wOF2"


def test_http_blocks_cross_site_posts(server):
    base, _ = server
    json_header = {"Content-Type": "application/json"}

    assert request(base + "/api/task", "POST", {"text": "x"})[0] == 415
    status, _ = request(base + "/api/task", "POST", {"text": "x"},
                        json_header | {"Origin": "https://evil.example"})
    assert status == 403
    status, _ = request(base + "/api/state", headers={"Host": "evil.example:8000"})
    assert status == 403


def test_http_switches_language(server):
    base, office = server
    status, body = request(base + "/api/lang", "POST", {"lang": "en"}, {"Content-Type": "application/json"})
    assert status == 200 and json.loads(body)["lang"] == "en"
    status, _ = request(base + "/api/lang", "POST", {"lang": "xx"}, {"Content-Type": "application/json"})
    assert status == 400


def test_http_reports_action_errors(server):
    base, _ = server
    status, body = request(base + "/api/review", "POST", {}, {"Content-Type": "application/json"})
    assert status == 400
    assert "задачу" in json.loads(body)["error"]
