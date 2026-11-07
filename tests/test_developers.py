"""The two developers: backren builds the backend, frontren the frontend, each in its own conversation."""

import json

import pytest

from office.agents import SKILLS_DIR, STATE_FILE, SUMMARY_FILE, Busy, Office

from .test_office import fake_claude, request, server  # noqa: F401 (fixtures)
from .test_office_features import MAJOR, all_args, arg, reviews, work

JSON = {"Content-Type": "application/json"}
REPORT = "Done: app.py prints hello. Run it with python3 app.py."  # what the fake developer says


def test_a_frontend_task_goes_to_frontren(fake_claude, tmp_path):  # noqa: F811
    office = Office(tmp_path / "ws")
    office.set_choice("frontend", "sonnet", "high")

    office.start_task("Make a landing page", "frontend")
    office.wait_idle()

    call = work(fake_claude())[0]
    assert "You are frontren" in arg(call, "--append-system-prompt")
    assert {"WebSearch", "WebFetch", "Skill"} <= set(arg(call, "--tools").split(","))
    assert all_args(call, "--plugin-dir") == [str(SKILLS_DIR / "developer"), str(SKILLS_DIR / "frontend")]
    assert (arg(call, "--model"), arg(call, "--effort")) == ("sonnet", "high")
    assert office.owner == "frontend"
    assert office.agents["frontend"]["bubble"] == "Done! Ready for review"
    assert office.agents["backend"]["bubble"] == "Waiting for a task"
    assert office._log[0]["text"] == "@frontren Make a landing page"


def test_backren_does_not_browse_the_web(fake_claude, tmp_path):  # noqa: F811
    office = Office(tmp_path / "ws")
    office.start_task("Add an API")
    office.wait_idle()

    call = work(fake_claude())[0]
    assert "You are backren" in arg(call, "--append-system-prompt")
    assert not {"WebSearch", "WebFetch"} & set(arg(call, "--tools").split(","))


def test_there_is_no_third_developer(tmp_path):
    office = Office(tmp_path / "ws")
    with pytest.raises(ValueError):
        office.start_task("x", "designer")
    assert office.task is None


def test_review_notes_go_back_to_the_developer_who_built_it(fake_claude, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", MAJOR)
    office = Office(tmp_path / "ws")
    office.start_task("Make a landing page", "frontend")
    office.wait_idle()
    office.request_review()
    office.wait_idle()

    office.send_rework()
    office.wait_idle()

    rework = work(fake_claude())[1]
    assert "You are frontren" in arg(rework, "--append-system-prompt")
    assert arg(rework, "--resume") == "sess-1"
    assert "Division by zero" in rework["prompt"]
    assert office.agents["frontend"]["bubble"] == "Done! Ready for review"
    assert any(e["text"] == "Sent the work back to frontren for fixes" for e in office._log)


def test_each_developer_has_its_own_conversation(fake_claude, tmp_path):  # noqa: F811
    office = Office(tmp_path / "ws")
    office.start_task("Add an API")
    office.wait_idle()
    office.start_task("Show the data on a page", "frontend")
    office.wait_idle()
    office.start_task("Add paging to the API")
    office.wait_idle()

    _, frontend, backend = work(fake_claude())
    assert "--resume" not in frontend["args"]  # frontren never was in backren's conversation
    assert arg(backend, "--resume") == "sess-1"


def test_a_developer_taking_over_hears_the_others_report_once(fake_claude, tmp_path):  # noqa: F811
    office = Office(tmp_path / "ws")
    office.start_task("Add an API")
    office.wait_idle()

    office.start_task("Show the data on a page", "frontend")
    office.wait_idle()
    office.start_task("Add a chart", "frontend")
    office.wait_idle()

    _, first, second = work(fake_claude())
    assert "backren's report on the work so far" in first["prompt"] and REPORT in first["prompt"]
    assert "backren's report" not in second["prompt"]


def test_reports_on_accepted_work_are_not_passed_on(fake_claude, tmp_path):  # noqa: F811
    office = Office(tmp_path / "ws")
    office.start_task("Add an API")
    office.wait_idle()
    office.accept()

    office.start_task("Make a landing page", "frontend")
    office.wait_idle()

    assert "report on the work so far" not in work(fake_claude())[1]["prompt"]


def test_one_developer_works_at_a_time(fake_claude, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("FAKE_CLAUDE_HANG", str(tmp_path / "child.pid"))
    office = Office(tmp_path / "ws")
    office.start_task("Add an API")

    with pytest.raises(Busy, match="backren is still working"):
        office.start_task("Make a page", "frontend")
    with pytest.raises(ValueError, match="frontren is not working"):
        office.stop("frontend")
    office.stop("backend")
    office.wait_idle()
    assert office.agents["backend"]["status"] == "idle"


def test_only_developers_and_the_idea_maker_can_be_stopped(tmp_path):
    with pytest.raises(ValueError, match="Only backren, frontren and idearen"):
        Office(tmp_path / "ws").stop("reviewer")


def test_the_history_says_who_built_each_task(fake_claude, tmp_path):  # noqa: F811
    office = Office(tmp_path / "ws")
    office.start_task("Make a landing page", "frontend")
    office.wait_idle()
    office.accept()

    assert office.history[-1]["by"] == "frontend"
    assert "Make a landing page (frontren)" in (tmp_path / "ws" / SUMMARY_FILE).read_text(encoding="utf-8")


def test_a_reopened_project_remembers_who_has_the_task(fake_claude, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", MAJOR)
    office = Office(tmp_path / "ws")
    office.start_task("Make a landing page", "frontend")
    office.wait_idle()
    office.request_review()
    office.wait_idle()
    office.send_rework()
    office.wait_idle()

    again = Office(tmp_path / "ws")
    again.request_review()
    again.wait_idle()

    assert again.owner == "frontend"
    assert REPORT in reviews(fake_claude())[-1]["prompt"]  # the re-review hears frontren's reply


def test_a_project_saved_with_one_developer_opens_with_backren(fake_claude, tmp_path):  # noqa: F811
    office = Office(tmp_path / "ws")
    office.start_task("x")
    office.wait_idle()
    state_file = tmp_path / "ws" / STATE_FILE
    state = json.loads(state_file.read_text())
    for key in ("owner", "reply"):
        del state[key]
    state["worker_reply"] = "the old developer's reply"
    state["history"] = [{"title": "old work", "commit": office.baseline, "time": 1.0}]
    state_file.write_text(json.dumps(state))

    again = Office(tmp_path / "ws")

    assert again.owner == "backend" and again.desks["backend"].reply == "the old developer's reply"
    assert [done["title"] for done in again.history] == ["old work"]


def test_http_task_and_stop_name_the_developer(server, fake_claude):  # noqa: F811
    base, office = server

    status, body = request(base + "/api/task", "POST", {"text": "Make a page", "developer": "frontend"}, JSON)
    assert status == 200 and json.loads(body)["owner"] == "frontend"
    office.wait_idle()

    assert request(base + "/api/task", "POST", {"text": "x", "developer": "boss"}, JSON)[0] == 400
    assert request(base + "/api/stop", "POST", {"agent": "frontend"}, JSON)[0] == 400  # not working now
    assert request(base + "/api/stop", "POST", {}, JSON)[0] == 400
