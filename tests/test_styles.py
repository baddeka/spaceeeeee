"""frontren's style directions: references turned into a few looks, and DESIGN.md for the one picked."""

import json

import pytest

from office.agents import SKILLS_DIR, Busy, Office
from office.designer import DESIGN_FILE, STYLE_TOOLS, design_md, parse_styles

from .test_office import fake_claude, request, server  # noqa: F401 (fixtures)
from .test_office_features import MAJOR, all_args, arg, reviews, work

JSON = {"Content-Type": "application/json"}


def style_calls(calls):
    return [c for c in calls if "--json-schema" in c["args"] and '"directions"' in arg(c, "--json-schema")]


def styled(tmp_path, brief="a pomodoro timer for students"):
    office = Office(tmp_path / "ws")
    office.propose_styles(brief)
    office.wait_idle()
    return office


def test_frontren_proposes_styles_and_changes_nothing(fake_claude, tmp_path):  # noqa: F811
    office = styled(tmp_path)

    call = style_calls(fake_claude())[0]
    assert arg(call, "--tools").split(",") == STYLE_TOOLS  # reads, searches, never writes
    assert "You are frontren" in arg(call, "--system-prompt")
    assert "a pomodoro timer for students" in call["prompt"]
    assert "--no-session-persistence" in call["args"]
    assert str(SKILLS_DIR / "frontend") in all_args(call, "--plugin-dir")
    assert "--strict-mcp-config" in call["args"]  # no Figma link, so no MCP servers
    assert [d["name"] for d in office.styles["directions"]] == ["Calm Paper", "Arcade Night", "Swiss Grid"]
    assert (office.styles["recommended"], office.styles["chosen"]) == (0, None)
    assert office.agents["frontend"]["status"] == "idle"
    assert office.agents["frontend"]["bubble"] == "Styles ready: 3. Pick one"
    assert office.desks["frontend"].session_id is None  # a one-off, not frontren's conversation
    assert not (tmp_path / "ws" / DESIGN_FILE).exists()


def test_unsafe_links_and_unknown_colors_are_dropped(fake_claude, tmp_path):  # noqa: F811
    office = styled(tmp_path)

    calm, arcade, _ = office.styles["directions"]
    assert [r["url"] for r in calm["references"]] == ["https://dribbble.com/shots/1-focus-timer"]
    assert "red" not in [s["hex"] for s in arcade["palette"]] and len(arcade["palette"]) == 3


def test_a_direction_without_a_usable_palette_is_left_out():
    keep = {"name": "A", "mood": "m", "summary": "s", "palette": [{"role": "bg", "hex": "#ffffff"},
            {"role": "text", "hex": "#000000"}], "heading_font": "Inter", "body_font": "Inter",
            "shapes": "s", "components": "c", "references": [], "fits": "f"}
    drop = {**keep, "name": "B", "palette": [{"role": "bg", "hex": "white"}]}

    directions, best = parse_styles({"directions": [drop, keep], "recommended": 1})

    assert [d["name"] for d in directions] == ["A"] and best == 0


def test_choosing_a_style_writes_design_md(fake_claude, tmp_path):  # noqa: F811
    office = styled(tmp_path)

    office.choose_style(2)

    design = (tmp_path / "ws" / DESIGN_FILE).read_text(encoding="utf-8")
    assert design.startswith("# Design: Swiss Grid")
    assert "| accent | `#d62828` |" in design and "- Headings: Manrope" in design
    assert office.styles["chosen"] == 2
    assert office.agents["frontend"]["bubble"] == "The style “Swiss Grid” is in DESIGN.md"
    assert office._log[-1]["text"] == "Chose the style “Swiss Grid” for DESIGN.md"


def test_a_design_md_that_cannot_be_written_is_reported(fake_claude, tmp_path):  # noqa: F811
    office = styled(tmp_path)
    (tmp_path / "ws" / DESIGN_FILE).mkdir()  # in the way, like a file another program holds

    with pytest.raises(ValueError, match="Could not write DESIGN.md"):
        office.choose_style(0)
    assert office.styles["chosen"] is None


def test_design_md_keeps_the_color_table_whole(fake_claude, tmp_path):  # noqa: F811
    office = styled(tmp_path)

    design = design_md(office.styles["directions"][0])

    assert "| accent / links | `#e0508a` |" in design
    assert "- Dribbble: focus timer: https://dribbble.com/shots/1-focus-timer (the big ring)" in design


def test_style_errors(fake_claude, tmp_path):  # noqa: F811
    office = Office(tmp_path / "ws")
    with pytest.raises(ValueError, match="Ask frontren for styles first"):
        office.choose_style(0)

    office.propose_styles("x")
    office.wait_idle()
    for bad in (-1, 3, "x", None):
        with pytest.raises(ValueError):
            office.choose_style(bad)


def test_frontren_looking_for_styles_takes_no_task_but_backren_can(fake_claude, tmp_path):  # noqa: F811
    office = Office(tmp_path / "ws")
    office.agents["frontend"]["status"] = "thinking"

    with pytest.raises(Busy, match="frontren is still working"):
        office.start_task("Make a page", "frontend")
    with pytest.raises(Busy):
        office.propose_styles("again")
    office.start_task("Add an API", "backend")
    office.wait_idle()
    assert office.agents["backend"]["bubble"] == "Done! Ready for review"


def test_a_style_search_can_be_stopped(fake_claude, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("FAKE_CLAUDE_HANG", str(tmp_path / "child.pid"))
    office = Office(tmp_path / "ws")
    office.propose_styles("x")
    assert office.agents["frontend"]["status"] == "thinking"

    office.stop("frontend")
    office.wait_idle()

    assert office.agents["frontend"]["status"] == "idle" and office.styles is None


def test_malformed_styles_are_reported(fake_claude, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("FAKE_CLAUDE_STYLES", json.dumps({"directions": [{"name": "half"}], "recommended": 0}))
    office = styled(tmp_path)

    assert office.styles is None
    assert office.agents["frontend"]["status"] == "idle"
    assert any(e["kind"] == "error" and "malformed styles" in e["text"] for e in office._log)


def test_the_autopilot_goes_on_once_frontren_has_its_styles(fake_claude, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", MAJOR)
    office = Office(tmp_path / "ws")
    office.start_task("Make a page", "frontend")
    office.wait_idle()
    office.request_review()
    office.wait_idle()
    office.agents["frontend"]["status"] = "thinking"  # looking for styles when the autopilot comes on
    office.set_autopilot(True, max_rounds=1)
    assert len(work(fake_claude())) == 1 and office.autopilot["round"] == 0  # the notes wait
    office.agents["frontend"]["status"] = "idle"

    office.propose_styles("x")
    office.wait_idle(30)

    assert len(work(fake_claude())) == 2  # the notes went back once the styles were ready
    assert office.autopilot["halted"] == "limit"


def test_new_styles_know_the_earlier_ones(fake_claude, tmp_path):  # noqa: F811
    office = styled(tmp_path)

    office.propose_styles("")
    office.wait_idle()

    prompt = style_calls(fake_claude())[-1]["prompt"]
    assert "Directions you already proposed" in prompt and "Calm Paper; Arcade Night; Swiss Grid" in prompt
    assert "work it out from the project" in prompt


def test_styles_survive_a_reopen(fake_claude, tmp_path):  # noqa: F811
    office = styled(tmp_path)
    office.choose_style(1)

    again = Office(tmp_path / "ws")

    assert again.styles == office.styles


FIGMA_LINK = "https://www.figma.com/design/AbC123/Timer?node-id=1-2"


def test_only_a_figma_link_brings_frontren_its_mcp_servers(fake_claude, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", MAJOR)
    office = Office(tmp_path / "ws")
    office.start_task("Make a page", "frontend")
    office.wait_idle()
    office.start_task(f"Make the page from {FIGMA_LINK}", "frontend")
    office.wait_idle()
    office.request_review()
    office.wait_idle()
    office.send_rework()
    office.wait_idle()
    office.propose_styles(f"like {FIGMA_LINK}")
    office.wait_idle()

    calls = fake_claude()
    plain, linked, rework = work(calls)
    assert "--strict-mcp-config" in plain["args"]
    for call in (linked, rework, style_calls(calls)[0]):  # a rework's notes don't repeat the link
        assert "--strict-mcp-config" not in call["args"]
        assert "mcp__claude_ai_Figma__get_screenshot" in call["args"] and "mcp__figma__use_figma" not in call["args"]


def test_the_other_agents_never_get_mcp_servers(fake_claude, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", json.dumps({"summary": "fine", "issues": []}))
    office = Office(tmp_path / "ws")
    office.start_task(f"Add an API for {FIGMA_LINK}")
    office.wait_idle()
    office.request_review()
    office.wait_idle()
    office.generate_ideas(FIGMA_LINK)
    office.wait_idle()

    calls = fake_claude()
    assert "--strict-mcp-config" in work(calls)[0]["args"]
    assert "--strict-mcp-config" in reviews(calls)[0]["args"]
    assert all("--strict-mcp-config" in c["args"] for c in calls if '"ideas"' in " ".join(c["args"]))


def test_http_styles(server, fake_claude):  # noqa: F811
    base, office = server

    assert request(base + "/api/style", "POST", {"index": 0}, JSON)[0] == 400
    status, _ = request(base + "/api/styles", "POST", {"brief": "a timer"}, JSON)
    assert status == 200
    office.wait_idle()
    status, body = request(base + "/api/style", "POST", {"index": 1}, JSON)
    assert status == 200 and json.loads(body)["styles"]["chosen"] == 1
