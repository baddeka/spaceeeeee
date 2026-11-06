import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from office import server as office_server
from office.agents import Busy, Office, _shorten, describe_tool, rework_prompt
from office.projects import Projects
from office.server import allowed_hosts, make_handler, page_url
from reviewer import claude_code, llm
from reviewer.claude_code import ClaudeCodeRun

from .conftest import process_gone, wait_for_file

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


def projects_with(office, tmp_path):
    """A project list with `office` already open, for the HTTP tests."""
    projects = Projects(tmp_path / "projects", lambda folder, lang: Office(folder, lang=lang), lang=office.lang)
    projects.office = office
    return projects


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


def test_claude_code_run_survives_large_stderr_and_prompt(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_NOISE", str(1 << 20))
    prompt = "x" * (1 << 20)

    result = ClaudeCodeRun(prompt, cwd=tmp_path, tools=[]).run()

    assert result.session_id == "sess-1"
    assert fake_claude()[0]["prompt"] == prompt


def test_stop_ends_the_commands_claude_code_started(fake_claude, tmp_path, monkeypatch):
    pid_file = tmp_path / "child.pid"
    monkeypatch.setenv("FAKE_CLAUDE_HANG", str(pid_file))
    run = ClaudeCodeRun("x", cwd=tmp_path, tools=[])
    errors = []
    thread = threading.Thread(target=lambda: _capture(errors, run.run))
    thread.start()
    child = int(wait_for_file(pid_file))

    run.stop()
    thread.join(10)

    assert not thread.is_alive()
    assert isinstance(errors[0], claude_code.ClaudeCodeStopped)
    assert process_gone(child)


def test_a_failing_event_handler_ends_the_run(fake_claude, tmp_path, monkeypatch):
    # Nobody reads the run after the error, so it must not keep editing files on its own.
    pid_file = tmp_path / "child.pid"
    monkeypatch.setenv("FAKE_CLAUDE_HANG", str(pid_file))

    def broken(event):
        wait_for_file(pid_file)
        raise RuntimeError("handler bug")

    started = time.monotonic()
    with pytest.raises(RuntimeError, match="handler bug"):
        ClaudeCodeRun("x", cwd=tmp_path, tools=[]).run(broken)

    assert time.monotonic() - started < 20
    assert process_gone(int(pid_file.read_text()))


def test_stop_before_start_prevents_the_run(fake_claude, tmp_path):
    run = ClaudeCodeRun("x", cwd=tmp_path, tools=[])
    run.stop()

    with pytest.raises(claude_code.ClaudeCodeError, match="stopped"):
        run.run()
    assert fake_claude() == []


def _capture(errors, fn):
    try:
        fn()
    except claude_code.ClaudeCodeError as e:
        errors.append(e)


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
    office.verdict = {"approved": True, "summary": "fine", "reasons": [], "checks": [], "issues": [{
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
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(projects_with(office, tmp_path)))
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}", office
    httpd.shutdown()
    httpd.server_close()


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
    assert status == 200 and "Rens Office" in html
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


def test_http_refuses_other_names_for_this_address(tmp_path):
    """DNS rebinding: a site points its own name at this address; the Host header gives it away."""
    office = make_office(tmp_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(projects_with(office, tmp_path), allowed_hosts("100.64.0.7", ["box.ts.net"])))
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        for host, expected in [("evil.example", 403), ("100.64.0.7", 200), ("box.ts.net", 200),
                               ("localhost", 200), ("[::1]", 200), ("[bad", 403)]:
            assert request(base + "/api/state", headers={"Host": f"{host}:8000"})[0] == expected, host
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_allowed_hosts_skip_wildcard_addresses():
    assert allowed_hosts("0.0.0.0") == allowed_hosts("::") == {"localhost", "127.0.0.1", "::1"}
    assert "fe80::1" in allowed_hosts("[FE80::1]")


def test_http_rejects_bad_bodies(server):
    base, _ = server
    json_header = {"Content-Type": "application/json"}

    assert request(base + "/api/lang", "POST", ["en"], json_header)[0] == 400
    req = urllib.request.Request(base + "/api/lang", data=b"{}", method="POST",
                                 headers=json_header | {"Content-Length": "abc"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=5)
    assert e.value.code == 400


def test_http_reports_unexpected_errors(server, monkeypatch):
    base, office = server

    def broken():
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(office, "accept", broken)
    status, body = request(base + "/api/accept", "POST", {}, {"Content-Type": "application/json"})
    assert status == 500 and "disk on fire" in json.loads(body)["error"]


def test_http_switches_language(server):
    base, _ = server
    status, body = request(base + "/api/lang", "POST", {"lang": "en"}, {"Content-Type": "application/json"})
    assert status == 200 and json.loads(body)["lang"] == "en"
    status, _ = request(base + "/api/lang", "POST", {"lang": "xx"}, {"Content-Type": "application/json"})
    assert status == 400


def test_http_reports_action_errors(server):
    base, _ = server
    status, body = request(base + "/api/review", "POST", {}, {"Content-Type": "application/json"})
    assert status == 400
    assert "задачу" in json.loads(body)["error"]


def test_shorten_handles_blank_and_long_text():
    assert _shorten("") == _shorten("  \n") == ""
    assert _shorten("first\nsecond") == "first"
    assert _shorten("x" * 100, 10) == "x" * 9 + "…"


def test_page_url_is_one_the_server_accepts():
    assert page_url("0.0.0.0", 8000) == "http://127.0.0.1:8000"
    assert page_url("::", 8000) == "http://127.0.0.1:8000"
    assert page_url("::1", 8000) == "http://[::1]:8000"
    assert page_url("100.64.0.7", 8000) == "http://100.64.0.7:8000"


def test_a_client_that_stops_talking_is_dropped(tmp_path, monkeypatch):
    monkeypatch.setattr(office_server, "SOCKET_TIMEOUT_SECONDS", 0.5)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(projects_with(make_office(tmp_path), tmp_path)))
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        with socket.create_connection(("127.0.0.1", httpd.server_port), timeout=5) as conn:
            conn.sendall(b"GET /api/state HTTP/1.1\r\nHost: 127.0.0.1\r\n")  # and then nothing
            assert conn.recv(1024) == b""  # the server hangs up instead of waiting forever
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_stop_only_stops_the_agent_it_names(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_HANG", str(tmp_path / "child.pid"))
    office = make_office(tmp_path)
    office.start_task("x")

    with pytest.raises(ValueError):
        office.stop("reviewer")
    assert office.agents["worker"]["status"] == "working"

    office.stop("worker")
    office.wait_idle()


def test_snapshot_does_not_share_the_live_verdict(tmp_path):
    office = make_office(tmp_path)
    office.verdict = {"approved": False, "summary": "bad", "reasons": [], "checks": [], "issues": [], "sent": False}

    snapshot = office.snapshot()
    office.verdict["sent"] = True

    assert snapshot["verdict"]["sent"] is False


def test_ipv6_addresses_get_an_ipv6_server():
    assert office_server.server_class("::1").address_family == socket.AF_INET6
    assert office_server.server_class("::").address_family == socket.AF_INET6
    assert office_server.server_class("127.0.0.1").address_family == socket.AF_INET


def test_an_ipv6_server_serves_the_page(tmp_path):
    try:
        httpd = office_server.server_class("::1")(("::1", 0), make_handler(projects_with(make_office(tmp_path), tmp_path)))
    except OSError:
        pytest.skip("no IPv6 on this machine")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        url = f"{page_url('::1', httpd.server_port)}/api/state"
        with urllib.request.urlopen(url, timeout=5) as response:
            assert response.status == 200
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_shutdown_stops_a_review_in_progress(fake_claude, tmp_path, monkeypatch):
    office = make_office(tmp_path)
    office.start_task("x")
    office.wait_idle()
    pid_file = tmp_path / "check.pid"
    (tmp_path / "ws" / ".ai-review.toml").write_text(f'checks = ["sleep 30 & echo $! > {pid_file}; wait"]\n')
    office.request_review()
    child = int(wait_for_file(pid_file))

    office.shutdown()

    assert process_gone(child)
    office.wait_idle()
    assert office.agents["reviewer"]["status"] != "reviewing"


def test_runs_started_after_shutdown_are_stopped(fake_claude, tmp_path):
    office = make_office(tmp_path)
    office.shutdown()

    office.start_task("x")
    office.wait_idle()

    assert fake_claude() == []
    assert office.agents["worker"]["status"] == "idle"


def test_shutdown_stops_the_running_agents(fake_claude, tmp_path, monkeypatch):
    pid_file = tmp_path / "child.pid"
    monkeypatch.setenv("FAKE_CLAUDE_HANG", str(pid_file))
    office = make_office(tmp_path)
    office.start_task("x")
    child = int(wait_for_file(pid_file))

    office.shutdown()
    office.wait_idle()

    assert office.agents["worker"]["status"] == "idle"
    assert process_gone(child)
