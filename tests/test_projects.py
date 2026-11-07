"""Projects: each one a folder that remembers its state, and the office that opens them."""

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from office.agents import LOG_FILE, STATE_FILE, SUMMARY_FILE, Busy, Office
from office.projects import Projects
from office.server import make_handler

from .test_office import fake_claude, request  # noqa: F401 (fixture)

JSON = {"Content-Type": "application/json"}
from .test_office_features import MAJOR, reviews, work


def test_a_reopened_project_has_its_task_verdict_ideas_and_log(fake_claude, tmp_path, monkeypatch):  # noqa: F811
    office = Office(tmp_path / "app")
    office.generate_ideas("study tools")
    office.wait_idle()
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", MAJOR)
    office.start_task("Build the timer")
    office.wait_idle()
    office.request_review()
    office.wait_idle()

    again = Office(tmp_path / "app")

    assert again.task == "Build the timer"
    assert again.baseline == office.baseline
    assert again.verdict["approved"] is False and again.verdict["issues"][0]["title"] == "Division by zero"
    assert [i["title"] for i in again.ideas] == [i["title"] for i in office.ideas]
    assert [e["text"] for e in again._log] == [e["text"] for e in office._log]
    assert all(a["status"] == "idle" for a in again.snapshot()["agents"].values())


def test_accepted_tasks_become_the_projects_history(fake_claude, tmp_path):  # noqa: F811
    office = Office(tmp_path / "app")
    office.start_task("Build the timer")
    office.wait_idle()
    office.accept()

    again = Office(tmp_path / "app")

    assert [done["title"] for done in again.snapshot()["history"]] == ["Build the timer"]
    assert again.task is None
    summary = (tmp_path / "app" / SUMMARY_FILE).read_text(encoding="utf-8")
    assert "Build the timer" in summary and "where we stopped" in summary


def test_a_fresh_conversation_gets_the_projects_past(fake_claude, tmp_path):  # noqa: F811
    office = Office(tmp_path / "app")
    office.start_task("Build the timer")
    office.wait_idle()
    office.accept()

    again = Office(tmp_path / "app")
    again.start_task("Add a pause button")
    again.wait_idle()
    again.accept()
    again.start_task("Add sounds")
    again.wait_idle()

    first, second = work(fake_claude())[1:]
    assert "picking up this project" in first["prompt"] and "- Build the timer" in first["prompt"]
    assert "picking up this project" not in second["prompt"]  # the conversation already knows


def test_a_rework_after_a_reopen_knows_the_task(fake_claude, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", MAJOR)
    office = Office(tmp_path / "app")
    office.start_task("Build the calculator")
    office.wait_idle()
    office.request_review()
    office.wait_idle()

    again = Office(tmp_path / "app")
    again.send_rework()
    again.wait_idle()

    prompt = work(fake_claude())[-1]["prompt"]
    assert "Build the calculator" in prompt and "Division by zero" in prompt


def test_a_re_review_after_a_reopen_hears_the_reply(fake_claude, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", MAJOR)
    office = Office(tmp_path / "app")
    office.start_task("x")
    office.wait_idle()
    office.request_review()
    office.wait_idle()
    office.send_rework()
    office.wait_idle()

    again = Office(tmp_path / "app")
    again.request_review()
    again.wait_idle()

    assert "The developer's reply" in reviews(fake_claude())[-1]["prompt"]


def test_ideas_after_a_reopen_are_new_ones(fake_claude, tmp_path):  # noqa: F811
    office = Office(tmp_path / "app")
    office.generate_ideas("study tools")
    office.wait_idle()

    again = Office(tmp_path / "app")
    again.generate_ideas("study tools")
    again.wait_idle()

    prompt = fake_claude()[-1]["prompt"]
    assert "Ideas already proposed" in prompt and "Habit tracker CLI" in prompt


def test_a_broken_state_opens_a_clean_project(tmp_path):
    folder = tmp_path / "app"
    (folder / STATE_FILE).parent.mkdir(parents=True)
    (folder / STATE_FILE).write_text("{not json")
    entry = {"agent": "user", "kind": "task", "text": "kept", "time": 1.0}
    (folder / LOG_FILE).write_text(json.dumps(entry) + "\n" + '{"agent": "user", "kin')

    office = Office(folder)

    assert office.task is None and office.verdict is None and office.history == []
    assert [e["text"] for e in office._log] == ["kept"]


@pytest.mark.parametrize("baseline", ["0" * 40, "not a sha", 42])
def test_a_baseline_gone_from_git_starts_over(tmp_path, baseline):
    folder = tmp_path / "app"
    (folder / STATE_FILE).parent.mkdir(parents=True)
    (folder / STATE_FILE).write_text(json.dumps({"baseline": baseline, "task": "old", "verdict": None}))

    office = Office(folder)

    assert office.baseline is None and office.task is None


def test_the_state_file_changes_only_with_the_state(fake_claude, tmp_path):  # noqa: F811
    office = Office(tmp_path / "app")
    office.start_task("x")
    office.wait_idle()
    state = tmp_path / "app" / STATE_FILE
    before = state.stat().st_mtime_ns

    office._set_agent("backend", bubble="just talking")

    assert state.stat().st_mtime_ns == before


# ---------- the project list ----------


@pytest.fixture
def projects(tmp_path, fake_claude):  # noqa: F811
    return Projects(tmp_path / "projects", lambda folder, lang: Office(folder, lang=lang))


def test_a_new_project_gets_its_own_folder(projects):
    projects.create("Timer app")

    folder = projects.root / "Timer app"
    assert projects.office.workspace == folder.resolve()
    assert (folder / ".git").is_dir()


def test_the_list_says_where_each_project_stands(projects):
    projects.create("first")
    projects.office.start_task("Build the timer")
    projects.office.wait_idle()
    projects.office.accept()
    projects.create("second")
    projects.office.start_task("Make a calculator")
    projects.office.wait_idle()
    projects.close()

    second, first = projects.list()
    assert (second["name"], second["task"], second["done"]) == ("second", "Make a calculator", 0)
    assert (first["name"], first["last_done"], first["done"]) == ("first", "Build the timer", 1)
    assert projects.snapshot()["project"] is None


@pytest.mark.parametrize("name", ["", "   "])
def test_a_new_project_needs_a_name(projects, name):
    with pytest.raises(ValueError):
        projects.create(name)


def test_a_new_project_does_not_take_over_an_old_one(projects):
    projects.create("app")
    projects.close()
    with pytest.raises(ValueError):
        projects.create("app")


def test_folders_that_hold_far_more_than_a_project_are_refused(projects, tmp_path):
    (tmp_path / "notes.txt").write_text("x")
    for folder in [Path.home(), Path(Path.home().anchor), projects.root, tmp_path / "notes.txt"]:
        with pytest.raises(ValueError):
            projects.open(folder)
    assert projects.office is None


def test_a_bare_name_opens_a_project_in_the_projects_folder(projects, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # where the server runs, which must never become a project

    projects.open(Path("my-app"))
    assert projects.office.workspace == (projects.root / "my-app").resolve()

    projects.close()
    with pytest.raises(ValueError):
        projects.open(Path(""))  # the projects folder itself
    assert not (tmp_path / ".git").exists()


def test_no_switch_while_the_agents_work(projects, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_HANG", str(tmp_path / "child.pid"))
    projects.create("busy")
    projects.office.start_task("x")

    with pytest.raises(Busy):
        projects.create("other")
    assert projects.office.workspace.name == "busy"
    projects.shutdown()


def test_a_switch_reloads_the_pages_and_keeps_the_limits(projects):
    projects.create("first")
    office_page, _ = projects.office.subscribe()
    projects.office.limits = [{"name": "five_hour", "used": 0.3, "resets_at": 1, "status": "allowed"}]
    projects.close()
    list_page = projects.wait_for_project()

    projects.create("second")

    assert {"type": "reload"} in _drain(office_page)
    assert {"type": "reload"} in _drain(list_page)
    assert projects.office.limits[0]["used"] == 0.3


def test_http_without_a_project(tmp_path, fake_claude):  # noqa: F811
    hub = Projects(tmp_path / "projects", lambda folder, lang: Office(folder, lang=lang))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(hub))
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}"
    try:
        state = json.loads(request(base + "/api/state")[1])
        assert state["project"] is None and state["projects"] == []
        assert request(base + "/api/task", "POST", {"text": "x"}, JSON)[0] == 409

        status, body = request(base + "/api/projects/new", "POST", {"name": "timer"}, JSON)
        assert status == 200 and json.loads(body)["project"]["name"] == "timer"
        assert request(base + "/api/projects/open", "POST", {"path": str(Path.home())}, JSON)[0] == 400
    finally:
        hub.shutdown()
        httpd.shutdown()
        httpd.server_close()


def _drain(q):
    events = []
    while not q.empty():
        events.append(q.get_nowait())
    return events
