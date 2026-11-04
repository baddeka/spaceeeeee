"""Skills, autopilot, fast fail and re-review in the office."""

import json

import pytest

from office.agents import SKILLS_DIR, Office, load_skills
from reviewer import llm
from reviewer.context import FileSnapshot, ReviewContext, collect_diff

from .test_office import fake_claude, request, server  # noqa: F401 (fixtures)

MAJOR = json.dumps({"summary": "bad", "issues": [{
    "severity": "major", "file": "app.py", "line": 1, "title": "Division by zero",
    "explanation": "divide(1, 0) crashes", "suggestion": "check b"}]})
CLEAN = json.dumps({"summary": "fine", "issues": []})


def reviews(calls):
    return [c for c in calls if "--json-schema" in c["args"]]


def work(calls):
    return [c for c in calls if "--json-schema" not in c["args"]]


def arg(call, flag):
    args = call["args"]
    return args[args.index(flag) + 1]


# ---------- skills ----------


def test_each_role_has_its_own_skills():
    worker = {s["name"] for s in load_skills("worker")}
    reviewer = {s["name"] for s in load_skills("reviewer")}

    assert {"test-first", "frontend-ui", "frontend-verify", "self-check"} <= worker
    assert {"security-review", "frontend-review", "verify-fixes"} <= reviewer
    assert not worker & reviewer
    for role in ("worker", "reviewer"):
        manifest = json.loads((SKILLS_DIR / role / ".claude-plugin" / "plugin.json").read_text())
        assert manifest["name"] == f"{role}-skills"
        assert all(s["description"] for s in load_skills(role))


def test_snapshot_lists_skills_with_labels_in_the_page_language(tmp_path):
    office = Office(tmp_path / "ws", lang="ru")
    labels = {s["name"]: s["label"] for s in office.snapshot()["skills"]["worker"]}

    assert labels["frontend-ui"].startswith("Верстает")
    office.set_language("en")
    labels = {s["name"]: s["label"] for s in office.snapshot()["skills"]["worker"]}
    assert labels["frontend-ui"].startswith("Builds pages")


def test_agents_get_their_plugin_and_the_skill_tool(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", CLEAN)
    office = Office(tmp_path / "ws")
    office.start_task("x")
    office.wait_idle()
    office.request_review()
    office.wait_idle()

    worker_call, review_call = fake_claude()
    assert arg(worker_call, "--plugin-dir") == str(SKILLS_DIR / "worker")
    assert "Skill" in arg(worker_call, "--tools").split(",")
    assert arg(review_call, "--plugin-dir") == str(SKILLS_DIR / "reviewer")
    assert arg(review_call, "--tools") == "Read,Grep,Glob,Skill"
    assert "frontend-review" in review_call["prompt"]


def test_skills_can_be_turned_off(fake_claude, tmp_path):
    office = Office(tmp_path / "ws", skills=False)
    office.start_task("x")
    office.wait_idle()

    assert "--plugin-dir" not in fake_claude()[0]["args"]
    assert office.snapshot()["skills"] == {"worker": [], "reviewer": [], "ideator": []}


def test_skill_in_use_is_tracked_and_logged(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_SKILL", "test-first")
    office = Office(tmp_path / "ws")
    seen = []
    original = office._set_agent

    def spy(agent, status=None, bubble=None):
        seen.append(office.agents[agent]["skill"])
        original(agent, status, bubble)

    office._set_agent = spy
    office.start_task("x")
    office.wait_idle()

    assert "test-first" in seen
    assert office.agents["worker"]["skill"] is None
    assert any(e["kind"] == "skill" and e["text"] == "Using skill: test-first" for e in office._log)


# ---------- autopilot ----------


def test_autopilot_stops_at_the_round_limit(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", MAJOR)
    office = Office(tmp_path / "ws")
    office.set_autopilot(True, max_rounds=2)

    office.start_task("Make divide")
    office.wait_idle(30)

    calls = fake_claude()
    assert len(work(calls)) == 3  # the task and two rounds of fixes
    assert len(reviews(calls)) == 3
    assert office.autopilot["halted"] == "limit"
    assert office.autopilot["round"] == 2
    assert office.verdict["approved"] is False and not office.verdict.get("sent")
    assert any("round limit" in e["text"] for e in office._log)


def test_autopilot_stops_when_approved(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", CLEAN)
    office = Office(tmp_path / "ws")
    office.set_autopilot(True)

    office.start_task("Make divide")
    office.wait_idle(30)

    calls = fake_claude()
    assert len(work(calls)) == 1 and len(reviews(calls)) == 1
    assert office.autopilot["halted"] == "approved"
    # Accepting stays with the person.
    assert "office: accepted" not in office._git("log", "--format=%s")


def test_turning_autopilot_on_continues_from_the_current_state(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", MAJOR)
    office = Office(tmp_path / "ws")
    office.start_task("x")
    office.wait_idle()
    office.request_review()
    office.wait_idle()
    assert office.verdict["approved"] is False

    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", CLEAN)
    office.set_autopilot(True, max_rounds=3)
    office.wait_idle(30)

    calls = fake_claude()
    assert len(work(calls)) == 2  # the rework it sent on its own
    assert office.autopilot == {"enabled": True, "max_rounds": 3, "round": 1, "halted": "approved"}


def test_autopilot_halts_on_worker_error(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_FAIL", "1")
    office = Office(tmp_path / "ws")
    office.set_autopilot(True)

    office.start_task("x")
    office.wait_idle()

    assert office.autopilot["halted"] == "error"
    assert reviews(fake_claude()) == []


def test_autopilot_rejects_bad_round_counts(tmp_path):
    office = Office(tmp_path / "ws")
    for bad in (0, 11, "many"):
        with pytest.raises(ValueError):
            office.set_autopilot(True, max_rounds=bad)


def test_http_autopilot(server):  # noqa: F811
    base, office = server
    status, body = request(
        base + "/api/autopilot", "POST", {"enabled": True, "max_rounds": 4},
        {"Content-Type": "application/json"},
    )
    assert status == 200
    assert json.loads(body)["autopilot"]["max_rounds"] == 4
    assert office.autopilot["enabled"] is True


# ---------- review optimizations ----------


def test_failing_checks_send_work_back_without_a_model_review(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    (tmp_path / "ws" / ".ai-review.toml").write_text('checks = ["echo boom; exit 1"]\n')
    office.start_task("x")
    office.wait_idle()

    office.request_review()
    office.wait_idle()

    assert reviews(fake_claude()) == []
    assert office.verdict["model"] == "checks"
    assert office.verdict["approved"] is False
    issue = office.verdict["issues"][0]
    assert issue["title"] == "Check failed: echo boom; exit 1"
    assert "boom" in issue["explanation"]


def test_fast_fail_can_be_turned_off(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", CLEAN)
    office = Office(tmp_path / "ws")
    (tmp_path / "ws" / ".ai-review.toml").write_text('checks = ["exit 1"]\nfast_fail = false\n')
    office.start_task("x")
    office.wait_idle()

    office.request_review()
    office.wait_idle()

    assert len(reviews(fake_claude())) == 1
    assert office.verdict["approved"] is False  # the failing check still blocks


def test_re_review_lists_the_previous_notes(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", MAJOR)
    office = Office(tmp_path / "ws")
    office.start_task("x")
    office.wait_idle()
    office.request_review()
    office.wait_idle()
    assert "# Notes from the previous review" not in reviews(fake_claude())[0]["prompt"]

    office.send_rework()
    office.wait_idle()
    office.request_review()
    office.wait_idle()

    second = reviews(fake_claude())[1]["prompt"]
    assert "# Notes from the previous review" in second
    assert "Division by zero" in second


def test_new_files_are_not_sent_twice(repo):
    (repo / "new.py").write_text("x = 1\n")

    ctx = collect_diff(repo)
    prompt = llm.build_prompt(ctx)

    assert ctx.files[0].is_new
    assert "+x = 1" in prompt
    assert "## new.py\n(new file: every line is in the diff above)" in prompt
    assert "## new.py\n```" not in prompt


def test_modified_files_still_include_full_content():
    ctx = ReviewContext("t", "+y\n", [FileSnapshot("a.py", "x = 1\ny\n")])

    assert "## a.py\n```\nx = 1\ny\n" in llm.build_prompt(ctx)


def test_phrases_with_values_switch_language_too(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", MAJOR)
    office = Office(tmp_path / "ws")
    office.start_task("x")
    office.wait_idle()
    office.request_review()
    office.wait_idle()
    assert office.agents["reviewer"]["bubble"] == "Needs fixes (1 serious)"

    office.set_language("ru")

    assert office.agents["reviewer"]["bubble"] == "Нужны правки (серьёзных: 1)"
    assert office.agents["worker"]["bubble"] == "Готово! Можно проверять"


def test_caches_stay_out_of_review_and_commits(tmp_path):
    office = Office(tmp_path / "ws")
    ws = tmp_path / "ws"
    (ws / "__pycache__").mkdir()
    (ws / "__pycache__" / "app.cpython-313.pyc").write_bytes(b"\0junk")
    (ws / "app.py").write_text("x = 1\n")

    assert [f.path for f in collect_diff(ws).files] == ["app.py"]
    Office(ws)  # a second start must not duplicate the patterns
    exclude = (ws / ".git" / "info" / "exclude").read_text()
    assert exclude.count("__pycache__/") == 1
    office._commit("snapshot")
    assert "__pycache__" not in office._git("ls-files")


def test_broken_project_config_does_not_leave_the_reviewer_stuck(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    (tmp_path / "ws" / ".ai-review.toml").write_text("checks = [unclosed\n")
    office.set_autopilot(True)
    office.start_task("x")
    office.wait_idle()

    assert office.agents["reviewer"]["status"] == "idle"
    assert office.agents["reviewer"]["bubble"] == "Could not review"
    assert office.autopilot["halted"] == "error"
    office.request_review()  # the office still accepts new actions
    office.wait_idle()


def test_without_bash_project_checks_do_not_run(fake_claude, tmp_path):
    # The developer can still write .ai-review.toml, so its commands would be Bash by another name.
    office = Office(tmp_path / "ws", worker_tools=["Read", "Write"])
    marker = tmp_path / "ran"
    (tmp_path / "ws" / ".ai-review.toml").write_text(f'checks = ["touch {marker}"]\n')
    office.start_task("x")
    office.wait_idle()

    office.request_review()
    office.wait_idle()

    assert not marker.exists()
    assert office.verdict["checks"] == []
    assert len(reviews(fake_claude())) == 1


def test_finished_agent_threads_are_not_kept(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    for _ in range(3):
        office.start_task("x")
        office.wait_idle()

    assert len(office._threads) <= 1


def test_stop_right_after_start_stops_the_run(fake_claude, tmp_path, monkeypatch):
    # The fake would wait for a minute; the stop must land even before its thread gets going.
    monkeypatch.setenv("FAKE_CLAUDE_HANG", str(tmp_path / "child.pid"))
    office = Office(tmp_path / "ws")
    office.start_task("x")
    office.stop("worker")
    office.wait_idle()

    assert office.agents["worker"]["status"] == "idle"
    assert office.agents["worker"]["bubble"] == "Stopped. Waiting for you"


def test_an_unexpected_error_does_not_leave_the_reviewer_busy(fake_claude, tmp_path, monkeypatch):
    office = Office(tmp_path / "ws")
    office.start_task("x")
    office.wait_idle()

    def broken(*args, **kwargs):
        raise RuntimeError("surprise")

    monkeypatch.setattr("office.agents.context.collect_diff", broken)
    office.request_review()
    office.wait_idle()

    assert office.agents["reviewer"]["status"] == "idle"
    assert office.agents["reviewer"]["bubble"] == "Could not review"
