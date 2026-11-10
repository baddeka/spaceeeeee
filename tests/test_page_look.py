"""The office looks at the project's page: a preview for the user, a check before the review, pictures for checkren."""

import json
import subprocess
import sys
import urllib.request

import pytest

from office import eyes
from office.agents import PREVIEW_DIR, STATE_FILE, Office, _touches_page
from office.eyes import find_browser

from .test_eyes import BROKEN, GOOD
from .test_office import fake_claude, request, server  # noqa: F401 (fixtures)
from .test_office_features import CLEAN, reviews, work

needs_browser = pytest.mark.skipif(find_browser() is None, reason="no Chrome, Edge or Chromium on this computer")
JSON = {"Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def quick_looks(monkeypatch):
    monkeypatch.setattr(eyes, "SETTLE_SECONDS", 0.1)


def page(tmp_path, monkeypatch, html):
    """Makes the fake developer write `html` as the project's index.html."""
    source = tmp_path / "page.html"
    source.write_text(html, encoding="utf-8")
    monkeypatch.setenv("FAKE_CLAUDE_PAGE", str(source))


@needs_browser
def test_the_office_shows_the_page_a_developer_built(fake_claude, tmp_path, monkeypatch):  # noqa: F811
    page(tmp_path, monkeypatch, GOOD)
    office = Office(tmp_path / "ws", preview_port=8123)
    office.start_task("Make a page", "frontend")
    office.wait_idle(30)

    preview = office.snapshot()["preview"]
    assert (preview["state"], preview["page"], preview["port"]) == ("ready", "index.html", 8123)
    assert preview["shots"] == [{"device": "desktop", "file": "desktop.png"}, {"device": "phone", "file": "phone.png"}]
    assert preview["problems"] == [] and preview["time"] > 0
    assert (tmp_path / "ws" / PREVIEW_DIR / "phone.png").read_bytes()[:4] == b"\x89PNG"
    assert ".rens-office" not in office._git("status", "--porcelain")  # the pictures never reach git

    again = Office(tmp_path / "ws")
    assert again.preview == office.preview  # and they are there when the project is opened again


@needs_browser
def test_a_broken_page_goes_back_without_a_review(fake_claude, tmp_path, monkeypatch):  # noqa: F811
    page(tmp_path, monkeypatch, BROKEN)
    office = Office(tmp_path / "ws")
    office.start_task("Make a page", "frontend")
    office.wait_idle(30)
    assert any("notDefined is not defined" in problem for problem in office.preview["problems"])

    office.request_review()
    office.wait_idle(30)

    assert reviews(fake_claude()) == []  # the model was not asked: the page will change anyway
    verdict = office.verdict
    assert verdict["approved"] is False
    assert verdict["checks"] == [{"command": "the page opens without errors and fits a phone", "passed": False}]
    assert "script error: ReferenceError: notDefined" in verdict["issues"][0]["explanation"]
    assert "wider than the screen" in verdict["issues"][0]["explanation"]
    assert "sh .rens-office/shot" in verdict["issues"][0]["suggestion"]
    assert len(office.preview["faint"]) == 1  # the same text on both screens is listed once

    office.send_rework()
    office.wait_idle(30)
    assert "the page is 326px wider than the screen" in work(fake_claude())[-1]["prompt"]


@needs_browser
def test_checkren_gets_the_pictures_of_a_page_that_opens(fake_claude, tmp_path, monkeypatch):  # noqa: F811
    page(tmp_path, monkeypatch, GOOD)
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", CLEAN)
    office = Office(tmp_path / "ws")
    office.start_task("Make a page", "frontend")
    office.wait_idle(30)
    office.request_review()
    office.wait_idle(30)

    prompt = reviews(fake_claude())[0]["prompt"]
    assert ".rens-office/preview/desktop.png, .rens-office/preview/phone.png" in prompt
    assert "design-review skill" in prompt
    assert office.verdict["checks"] == [{"command": "the page opens without errors and fits a phone", "passed": True}]
    assert office.verdict["approved"] is True


def test_a_project_without_a_page_has_no_preview_and_no_page_check(fake_claude, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", CLEAN)
    office = Office(tmp_path / "ws")
    office.start_task("Add an API")
    office.wait_idle()
    office.request_review()
    office.wait_idle()

    assert office.preview is None and office.verdict["checks"] == []
    assert "preview/" not in reviews(fake_claude())[0]["prompt"]


def test_no_browser_means_no_page_check_but_the_review_goes_on(fake_claude, tmp_path, monkeypatch):  # noqa: F811
    page(tmp_path, monkeypatch, GOOD)
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", CLEAN)
    monkeypatch.setattr(eyes, "find_browser", lambda: None)
    office = Office(tmp_path / "ws")
    office.start_task("Make a page", "frontend")
    office.wait_idle()
    assert office.preview["state"] == "no_browser" and "shots" not in office.preview

    office.request_review()
    office.wait_idle()

    assert office.verdict["approved"] is True and office.verdict["checks"] == []


@pytest.mark.parametrize("off", ["flag", "config"])
def test_the_look_can_be_turned_off(fake_claude, tmp_path, monkeypatch, off):  # noqa: F811
    page(tmp_path, monkeypatch, BROKEN)
    monkeypatch.setenv("FAKE_CLAUDE_REVIEW", CLEAN)
    monkeypatch.setattr(eyes, "look", lambda *a, **k: pytest.fail("the page was looked at"))
    office = Office(tmp_path / "ws", look=off != "flag")
    if off == "config":
        (tmp_path / "ws" / ".ai-review.toml").write_text("page_check = false\n")
        monkeypatch.setattr(office, "_show_page", lambda: None)  # the config only speaks of the review
    office.start_task("Make a page", "frontend")
    office.wait_idle()
    office.request_review()
    office.wait_idle()

    assert office.verdict["approved"] is True and office.verdict["checks"] == []


def test_a_change_without_page_files_is_not_looked_at():
    assert not _touches_page("diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n+x = 1\n")
    assert _touches_page("diff --git a/web/a.css b/web/a.css\n--- /dev/null\n+++ b/web/a.css\n+body{}\n")
    assert not _touches_page("+++ b/notes.md\n+a line that mentions style.css\n")


def test_a_saved_preview_without_its_pictures_is_dropped(tmp_path):
    folder = tmp_path / "ws"
    (folder / STATE_FILE).parent.mkdir(parents=True)
    saved = {"state": "ready", "page": "index.html", "shots": [{"device": "desktop", "file": "desktop.png"}],
             "problems": [], "faint": [], "time": 1.0}
    (folder / STATE_FILE).write_text(json.dumps({"preview": saved}))

    assert Office(folder).preview is None

    (folder / PREVIEW_DIR).mkdir()
    (folder / PREVIEW_DIR / "desktop.png").write_bytes(b"\x89PNG")
    assert Office(folder).preview == saved
    (folder / STATE_FILE).write_text(json.dumps({"preview": {**saved, "shots": [{"device": "x", "file": "../state.json"}]}}))
    assert Office(folder).preview is None


@pytest.mark.skipif(sys.platform == "win32", reason="the launcher is a shell script")
def test_every_project_gets_the_shot_tool(tmp_path):
    Office(tmp_path / "my project")

    launcher = tmp_path / "my project" / ".rens-office" / "shot"
    ran = subprocess.run(["sh", str(launcher), "--help"], capture_output=True, text=True, cwd=tmp_path / "my project")
    assert ran.returncode == 0 and "click=SELECTOR" in ran.stdout
    assert sys.executable in (launcher.parent / "shot.cmd").read_text()


@needs_browser
def test_http_serves_the_pictures_and_looks_again(server, fake_claude, tmp_path, monkeypatch):  # noqa: F811
    base, office = server
    assert request(base + "/preview/desktop.png")[0] == 404

    (office.workspace / "index.html").write_text(GOOD, encoding="utf-8")
    assert request(base + "/api/preview", "POST", {}, JSON)[0] == 200
    office.wait_idle(30)

    with urllib.request.urlopen(base + "/preview/desktop.png", timeout=5) as picture:
        assert picture.status == 200 and picture.headers["Content-Type"] == "image/png"
        assert picture.read()[:4] == b"\x89PNG"
    for path in ["/preview/../state.json", "/preview/..%2fstate.json", "/preview/desktop.txt"]:
        assert request(base + path)[0] == 404
