"""Skills, autopilot, fast fail and re-review in the office."""

import json

import pytest

from office.agents import SKILLS_DIR, Office, limit_windows, load_skills
from office.i18n import MESSAGES
from reviewer import claude_code, llm
from reviewer.context import FileSnapshot, ReviewContext, collect_diff

from .conftest import wait_for_file
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


def all_args(call, flag):
    args = call["args"]
    return [args[n + 1] for n, a in enumerate(args) if a == flag]


# ---------- skills ----------


def test_each_role_has_its_own_skills(tmp_path):
    skills = {role: {s["name"] for s in found} for role, found in Office(tmp_path / "ws").skills.items()}
    shared = {
        "project-setup", "test-driven-development", "systematic-debugging", "verification-before-completion",
        "receiving-code-review",
    }

    assert shared | {"api-design", "data-model", "ponytail"} == skills["backend"]
    assert shared | {
        "frontend-design", "frontend-ui", "frontend-verify", "design-directions",
        "match-reference", "ui-kit", "ux-copy", "motion", "visual-craft",
    } == skills["frontend"]
    assert {"security-review", "frontend-review", "verify-fixes"} <= skills["reviewer"]
    assert {"brainstorm", "write-brief", "ui-brief"} <= skills["ideator"]
    assert not (skills["backend"] | skills["frontend"]) & skills["reviewer"]
    for plugin in ("developer", "backend", "frontend", "reviewer", "ideator"):
        manifest = json.loads((SKILLS_DIR / plugin / ".claude-plugin" / "plugin.json").read_text())
        assert manifest["name"] == f"{plugin}-skills"
        assert all(s["description"] for s in load_skills(plugin))


def test_every_skill_has_a_label_in_both_languages(tmp_path):
    office = Office(tmp_path / "ws")
    names = {s["name"] for found in office.skills.values() for s in found}

    assert all(f"skill_{name}" in MESSAGES["en"] and f"skill_{name}" in MESSAGES["ru"] for name in names)


def test_snapshot_lists_skills_with_labels_in_the_page_language(tmp_path):
    office = Office(tmp_path / "ws", lang="ru")
    labels = {s["name"]: s["label"] for s in office.snapshot()["skills"]["frontend"]}

    assert labels["frontend-ui"].startswith("Верстает")
    office.set_language("en")
    labels = {s["name"]: s["label"] for s in office.snapshot()["skills"]["frontend"]}
    assert labels["frontend-ui"].startswith("Builds pages")


def test_agents_get_their_plugin_and_the_skill_tool(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", CLEAN)
    office = Office(tmp_path / "ws")
    office.start_task("x")
    office.wait_idle()
    office.request_review()
    office.wait_idle()

    dev_call, review_call = fake_claude()
    assert all_args(dev_call, "--plugin-dir") == [str(SKILLS_DIR / "developer"), str(SKILLS_DIR / "backend")]
    assert "Skill" in arg(dev_call, "--tools").split(",")
    assert arg(review_call, "--plugin-dir") == str(SKILLS_DIR / "reviewer")
    assert arg(review_call, "--tools") == "Read,Grep,Glob,Skill"
    assert "frontend-review" in review_call["prompt"]


def test_skills_can_be_turned_off(fake_claude, tmp_path):
    office = Office(tmp_path / "ws", skills=False)
    office.start_task("x")
    office.wait_idle()

    assert "--plugin-dir" not in fake_claude()[0]["args"]
    assert office.snapshot()["skills"] == {"backend": [], "frontend": [], "reviewer": [], "ideator": []}


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
    assert office.agents["backend"]["skill"] is None
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


def test_autopilot_halts_on_developer_error(fake_claude, tmp_path, monkeypatch):
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
    assert office.agents["backend"]["bubble"] == "Готово! Можно проверять"


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
    office = Office(tmp_path / "ws", developer_tools=["Read", "Write"])
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
    office.stop("backend")
    office.wait_idle()

    assert office.agents["backend"]["status"] == "idle"
    assert office.agents["backend"]["bubble"] == "Stopped. Waiting for you"


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


def test_re_review_hears_the_developers_reply(fake_claude, tmp_path, monkeypatch):
    office = Office(tmp_path / "ws")
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", MAJOR)
    office.start_task("x")
    office.wait_idle()
    office.request_review()
    office.wait_idle()
    office.send_rework()
    office.wait_idle()

    office.request_review()
    office.wait_idle()

    first, second = reviews(fake_claude())
    assert "The developer's reply" not in first["prompt"]
    assert "The developer's reply" in second["prompt"]
    assert "Done: app.py prints hello" in second["prompt"]


def test_project_effort_applies_to_the_review(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    (tmp_path / "ws" / ".ai-review.toml").write_text('effort = "low"\n')
    office.start_task("x")
    office.wait_idle()

    office.request_review()
    office.wait_idle()

    assert arg(reviews(fake_claude())[0], "--effort") == "low"


def test_turning_autopilot_on_hands_over_waiting_ideas(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    office.generate_ideas("study tools")
    office.wait_idle()
    assert office.task is None

    office.set_autopilot(True, max_rounds=1)
    office.wait_idle()

    assert office.task_title == "Focus timer page"


# What Claude Code 2.1 reports for a subscription, trimmed: the windows are what the page shows.
RATE_LIMIT_INFO = {
    "status": "allowed",
    "resetsAt": 1793865600,
    "isUsingOverage": False,
    "unifiedWindows": {
        "seven_day": {"utilization": 0.28, "resetsAt": 1793937600, "status": "allowed"},
        "five_hour": {"utilization": 0.05, "resetsAt": 1793870400, "status": "allowed"},
    },
}


def test_limit_windows_come_shortest_first():
    assert limit_windows(RATE_LIMIT_INFO) == [
        {"name": "five_hour", "used": 0.05, "resets_at": 1793870400, "status": "allowed"},
        {"name": "seven_day", "used": 0.28, "resets_at": 1793937600, "status": "allowed"},
    ]
    assert limit_windows({"status": "allowed"}) == []
    assert limit_windows({"unifiedWindows": {"five_hour": {"status": "allowed"}}}) == []
    assert limit_windows(None) == limit_windows(["odd"]) == []


def test_agent_runs_report_the_subscription_limits(fake_claude, tmp_path, monkeypatch):
    office = Office(tmp_path / "ws")
    assert office.snapshot()["limits"] is None
    monkeypatch.setenv("FAKE_CLAUDE_RATE_LIMIT", json.dumps(RATE_LIMIT_INFO))

    office.start_task("x")
    office.wait_idle()

    limits = office.snapshot()["limits"]
    assert [w["name"] for w in limits] == ["five_hour", "seven_day"]
    assert limits[1]["used"] == 0.28


def test_the_limits_check_is_one_tiny_request(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_RATE_LIMIT", json.dumps(RATE_LIMIT_INFO))
    office = Office(tmp_path / "ws")

    office.refresh_limits()
    office.wait_idle()

    snapshot = office.snapshot()
    assert [w["name"] for w in snapshot["limits"]] == ["five_hour", "seven_day"]
    assert snapshot["limits_checking"] is False
    (call,) = fake_claude()
    assert arg(call, "--model") == "haiku"
    assert arg(call, "--tools") == ""
    assert "--no-session-persistence" in call["args"]
    assert not (tmp_path / "ws" / "app.py").exists()


def test_a_failed_limits_check_only_leaves_them_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(claude_code, "CLAUDE_BIN", str(tmp_path / "no-such-claude"))
    office = Office(tmp_path / "ws")

    office.refresh_limits()
    office.wait_idle()

    snapshot = office.snapshot()
    assert snapshot["limits"] is None and snapshot["limits_checking"] is False
    assert "Could not read the subscription limits" in office._log[-1]["text"]


def test_one_limits_check_at_a_time(fake_claude, tmp_path, monkeypatch):
    pid_file = tmp_path / "child.pid"
    monkeypatch.setenv("FAKE_CLAUDE_HANG", str(pid_file))
    office = Office(tmp_path / "ws")

    office.refresh_limits()
    wait_for_file(pid_file)
    office.refresh_limits()

    assert len(fake_claude()) == 1
    assert office.snapshot()["limits_checking"] is True
    office.shutdown()


def test_http_limits_check(server, fake_claude):  # noqa: F811
    base, office = server
    status, _ = request(base + "/api/limits", "POST", {}, {"Content-Type": "application/json"})
    office.wait_idle()

    assert status == 200
    assert arg(fake_claude()[0], "--model") == "haiku"


# ---------- model and effort per agent ----------


def test_each_agent_runs_with_its_own_model_and_effort(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    office.set_choice("backend", "sonnet", "low")
    office.set_choice("reviewer", "opus", "xhigh")

    office.start_task("x")
    office.wait_idle()
    office.request_review()
    office.wait_idle()

    dev, reviewer = work(fake_claude())[0], reviews(fake_claude())[0]
    assert (arg(dev, "--model"), arg(dev, "--effort")) == ("sonnet", "low")
    assert (arg(reviewer, "--model"), arg(reviewer, "--effort")) == ("opus", "xhigh")


def test_auto_falls_back_to_the_command_line_then_to_defaults(fake_claude, tmp_path):
    office = Office(tmp_path / "ws", model="haiku")
    office.set_choice("backend", None, "medium")

    office.start_task("x")
    office.wait_idle()
    office.request_review()
    office.wait_idle()

    dev, reviewer = work(fake_claude())[0], reviews(fake_claude())[0]
    assert (arg(dev, "--model"), arg(dev, "--effort")) == ("haiku", "medium")
    assert arg(reviewer, "--model") == "haiku"
    assert arg(reviewer, "--effort") == "high"  # the reviewer's own default
    assert office.snapshot()["defaults"] == {"model": "haiku", "effort": None}


def test_choices_are_checked(tmp_path):
    office = Office(tmp_path / "ws")
    for agent, model, effort in [("worker", "opus", None), ("backend", "gpt", None), ("frontend", None, "huge")]:
        with pytest.raises(ValueError):
            office.set_choice(agent, model, effort)
    assert office.choices["backend"] == {"model": None, "effort": None}


def test_choices_stay_after_a_restart(tmp_path):
    saved = tmp_path / "choices.json"
    Office(tmp_path / "ws", choices_file=saved).set_choice("ideator", "haiku", "low")

    again = Office(tmp_path / "ws", choices_file=saved)

    assert again.snapshot()["choices"]["ideator"] == {"model": "haiku", "effort": "low"}
    assert again.choices["backend"] == {"model": None, "effort": None}


def test_a_broken_choices_file_means_auto(tmp_path):
    saved = tmp_path / "choices.json"
    saved.write_text('{"agents": {"worker": {"model": "gpt-9", "effort": "low"}, "reviewer": [1]}')  # not even JSON

    office = Office(tmp_path / "ws", choices_file=saved)
    assert office.choices["backend"] == {"model": None, "effort": None}

    saved.write_text('{"agents": {"worker": {"model": "gpt-9", "effort": "low"}, "reviewer": [1]}}')
    office = Office(tmp_path / "ws", choices_file=saved)
    assert office.choices["backend"] == {"model": None, "effort": "low"}
    assert office.choices["reviewer"] == {"model": None, "effort": None}


def test_http_choice(server):  # noqa: F811
    base, _ = server
    json_header = {"Content-Type": "application/json"}

    status, body = request(base + "/api/choice", "POST", {"agent": "backend", "model": "opus", "effort": ""}, json_header)
    assert status == 200 and json.loads(body)["choices"]["backend"] == {"model": "opus", "effort": None}
    assert request(base + "/api/choice", "POST", {"agent": "backend", "model": "gpt"}, json_header)[0] == 400


# ---------- commit author ----------


def _git_config(monkeypatch, tmp_path, text):
    """Points git at a global config of its own, so the machine's settings don't leak in."""
    config = tmp_path / "gitconfig"
    config.write_text(text)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def test_commits_go_out_under_the_users_git_name(tmp_path, monkeypatch):
    _git_config(monkeypatch, tmp_path, "[user]\n\tname = baddeka\n\temail = 1+baddeka@users.noreply.github.com\n")
    office = Office(tmp_path / "ws")

    office._commit("office: before task")

    assert office._git("log", "-1", "--format=%an <%ae>") == "baddeka <1+baddeka@users.noreply.github.com>"


def test_commits_fall_back_to_the_office_name(tmp_path, monkeypatch):
    _git_config(monkeypatch, tmp_path, "[user]\n\tname = only-a-name\n")
    office = Office(tmp_path / "ws")

    office._commit("office: before task")

    assert office._git("log", "-1", "--format=%an <%ae>") == "Rens Office <office@localhost>"
