"""The idea maker: ideas from a topic, handing them to the developer, and the autopilot."""

import json

import pytest

from office.agents import SKILLS_DIR, STATE_FILE, Busy, Office
from office.i18n import MESSAGES
from office.ideator import IdeasError, parse_ideas

from .test_office import fake_claude, request, server  # noqa: F401 (fixtures)

CLEAN = json.dumps({"summary": "fine", "issues": []})
MAJOR = json.dumps({"summary": "bad", "issues": [{
    "severity": "major", "file": "app.py", "line": 1, "title": "Bug",
    "explanation": "breaks", "suggestion": "fix"}]})


def schema_of(call):
    args = call["args"]
    return args[args.index("--json-schema") + 1] if "--json-schema" in args else ""


def ideator_calls(calls):
    return [c for c in calls if '"ideas"' in schema_of(c)]


def dev_calls(calls):
    return [c for c in calls if not schema_of(c)]


def arg(call, flag):
    return call["args"][call["args"].index(flag) + 1]


def idea(title="T", scope="small"):
    return {"title": title, "pitch": "p", "why": "w", "scope": scope, "developer": "backend", "ui": "", "task": "do it"}


# ---------- parsing ----------


def test_parse_ideas_marks_exactly_one_recommended():
    ideas = parse_ideas({"ideas": [idea("A"), idea("B")], "recommended": 1})

    assert [i["recommended"] for i in ideas] == [False, True]
    assert not any(i["handed"] for i in ideas)


def test_out_of_range_recommendation_falls_back_to_the_first():
    ideas = parse_ideas({"ideas": [idea("A"), idea("B")], "recommended": 7})

    assert ideas[0]["recommended"] and not ideas[1]["recommended"]


@pytest.mark.parametrize("bad", [None, {"ideas": [], "recommended": 0}, {"ideas": [{"title": "x"}]}])
def test_unusable_answers_are_errors(bad):
    with pytest.raises(IdeasError):
        parse_ideas(bad)


# ---------- generating ----------


def test_topic_turns_into_ideas(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")

    office.generate_ideas("productivity for students")
    office.wait_idle()

    state = office.snapshot()
    assert state["agents"]["ideator"]["status"] == "ready"
    assert state["agents"]["ideator"]["bubble"] == "Ideas ready: 3"
    assert state["topic"] == "productivity for students"
    assert [i["title"] for i in state["ideas"]] == ["Habit tracker CLI", "Focus timer page", "Expense splitter"]
    assert state["ideas"][1]["recommended"]

    call = ideator_calls(fake_claude())[0]
    assert "Topic: productivity for students" in call["prompt"]
    assert call["prompt"].endswith("Reply in English.")
    assert "idea maker" in arg(call, "--system-prompt")
    assert arg(call, "--plugin-dir") == str(SKILLS_DIR / "ideator")
    assert {"WebSearch", "Skill", "Read"} <= set(arg(call, "--tools").split(","))
    assert "Write" not in arg(call, "--tools") and "Bash" not in arg(call, "--tools")
    assert any(e["kind"] == "skill" and "brainstorm" in e["text"] for e in office._log)


def test_asking_again_continues_the_idea_makers_conversation(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    office.generate_ideas("games")
    office.wait_idle()
    office.generate_ideas("more games")
    office.wait_idle()

    first, second = ideator_calls(fake_claude())
    assert "--resume" not in first["args"]
    assert arg(second, "--resume") == "sess-1"


def test_idea_maker_thinks_while_the_developer_works(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    office.start_task("x")
    office.generate_ideas("anything")  # no Busy: it only reads

    with pytest.raises(Busy):
        office.generate_ideas("again")
    office.wait_idle()
    with pytest.raises(ValueError):
        office.generate_ideas("   ")


def test_a_failed_run_keeps_the_previous_topic_with_its_ideas(fake_claude, tmp_path, monkeypatch):
    office = Office(tmp_path / "ws")
    office.generate_ideas("games")
    office.wait_idle()
    monkeypatch.setenv("FAKE_CLAUDE_FAIL", "1")

    office.generate_ideas("cooking")
    office.wait_idle()

    assert office.topic == "games"
    assert len(office.ideas) == 3


def test_failed_ideation_returns_to_idle(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_IDEAS", json.dumps({"ideas": [], "recommended": 0}))
    office = Office(tmp_path / "ws")

    office.generate_ideas("x")
    office.wait_idle()

    assert office.agents["ideator"]["status"] == "idle"
    assert office.agents["ideator"]["bubble"] == "Could not come up with ideas"
    assert office.ideas is None


# ---------- handing off ----------


def test_handing_off_gives_the_developer_the_brief(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    office.generate_ideas("productivity")
    office.wait_idle()

    office.hand_off(1)
    office.wait_idle()

    call = dev_calls(fake_claude())[0]
    prompt = call["prompt"]
    assert prompt.startswith("Idea from idearen: Focus timer page")
    assert "Build index.html with a 25/5 timer" in prompt
    assert "Interface:\nOne screen: a big countdown ring." in prompt
    assert "not from the user" in prompt  # the brief may carry text from the web
    assert "You are frontren" in arg(call, "--append-system-prompt")  # idearen picked the frontend
    assert office.ideas[1]["handed"] and not office.ideas[0]["handed"]
    assert office.agents["ideator"]["bubble"] == "Handed to frontren: Focus timer page"
    assert any(e["agent"] == "ideator" and e["kind"] == "handoff" for e in office._log)

    office.accept()
    assert "office: accepted: Focus timer page" in office._git("log", "--format=%s")
    assert office.task is None


def test_hand_off_errors(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    with pytest.raises(ValueError):
        office.hand_off(0)

    office.generate_ideas("x")
    office.wait_idle()
    for bad in (-1, 3, "x", None):
        with pytest.raises(ValueError):
            office.hand_off(bad)

    office.agents["backend"]["status"] = "working"
    with pytest.raises(Busy):
        office.hand_off(0)


def test_an_idea_can_go_to_the_other_developer(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    office.generate_ideas("productivity")
    office.wait_idle()

    office.hand_off(1, "backend")
    office.wait_idle()

    assert "You are backren" in arg(dev_calls(fake_claude())[0], "--append-system-prompt")
    assert office.owner == "backend" and office.ideas[1]["developer"] == "backend"
    assert office.agents["ideator"]["bubble"] == "Handed to backren: Focus timer page"


def test_ideas_saved_before_two_developers_still_open(tmp_path):
    folder = tmp_path / "ws"
    (folder / STATE_FILE).parent.mkdir(parents=True)
    old = {"title": "Old", "pitch": "p", "why": "w", "scope": "small", "task": "t", "recommended": True, "handed": False}
    (folder / STATE_FILE).write_text(json.dumps({"topic": "x", "ideas": [old, {**old, "developer": "designer"}]}))

    office = Office(folder)

    assert office.ideas == [{**old, "developer": "backend", "ui": ""}]


def test_stopping_the_idea_maker_when_it_is_idle(tmp_path):
    with pytest.raises(ValueError):
        Office(tmp_path / "ws").stop("ideator")


# ---------- autopilot ----------


def test_autopilot_builds_the_recommended_idea(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", CLEAN)
    office = Office(tmp_path / "ws")
    office.set_autopilot(True)

    office.generate_ideas("productivity")
    office.wait_idle(30)

    calls = fake_claude()
    assert "25/5 timer" in dev_calls(calls)[0]["prompt"]
    assert office.ideas[1]["handed"]
    assert office.autopilot["halted"] == "approved"
    assert any("recommended idea" in e["text"] for e in office._log)


def test_autopilot_does_not_start_an_idea_over_unaccepted_work(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", MAJOR)
    office = Office(tmp_path / "ws")
    office.set_autopilot(True, max_rounds=1)
    office.start_task("x")
    office.wait_idle(30)
    assert office.autopilot["halted"] == "limit"

    office.generate_ideas("anything")
    office.wait_idle()

    assert not any(i["handed"] for i in office.ideas)


# ---------- language and HTTP ----------


def test_idea_maker_bubble_switches_language(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    office.generate_ideas("x")
    office.wait_idle()

    office.set_language("ru")

    assert office.agents["ideator"]["bubble"] == "Идей готово: 3"


def test_every_text_exists_in_both_languages():
    assert set(MESSAGES["en"]) == set(MESSAGES["ru"])


def test_http_ideas_and_handoff(fake_claude, server):  # noqa: F811
    base, office = server
    json_header = {"Content-Type": "application/json"}

    status, _ = request(base + "/api/ideas", "POST", {"topic": "games"}, json_header)
    assert status == 200
    office.wait_idle()
    status, body = request(base + "/api/handoff", "POST", {"index": 0}, json_header)
    assert status == 200
    assert json.loads(body)["agents"]["backend"]["status"] == "working"
    office.wait_idle()
    status, body = request(base + "/api/handoff", "POST", {"index": 2, "developer": "frontend"}, json_header)
    assert status == 200
    assert json.loads(body)["agents"]["frontend"]["status"] == "working"
    office.wait_idle()
    assert request(base + "/api/handoff", "POST", {"index": 9}, json_header)[0] == 400
    assert request(base + "/api/handoff", "POST", {"index": 1, "developer": "boss"}, json_header)[0] == 400


def test_agents_know_their_names(fake_claude, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", CLEAN)
    office = Office(tmp_path / "ws")
    office.generate_ideas("x")
    office.wait_idle()
    office.hand_off(0)
    office.wait_idle()
    office.request_review()
    office.wait_idle()

    calls = fake_claude()
    assert "You are idearen" in arg(ideator_calls(calls)[0], "--system-prompt")
    assert "You are backren" in arg(dev_calls(calls)[0], "--append-system-prompt")
    review = next(c for c in calls if schema_of(c) and '"ideas"' not in schema_of(c))
    assert "you are checkren" in review["prompt"]
