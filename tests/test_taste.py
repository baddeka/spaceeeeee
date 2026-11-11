"""frontren's design skill: Taste Skill fetched once at a pinned version, or frontren's own skills."""

import subprocess

import pytest

from office import taste
from office.agents import SKILLS_DIR, Office

from .test_office import fake_claude  # noqa: F401 (fixture)
from .test_office_features import all_args, arg, work


@pytest.fixture
def upstream(tmp_path, monkeypatch):
    """A local stand-in for the Taste Skill repository, pinned at its one commit."""
    repo = tmp_path / "upstream"
    skill = repo / "skills" / "taste-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: design-taste-frontend\ndescription: d\n---\n# Taste\n")
    (repo / "LICENSE").write_text("MIT License")

    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()

    git("init", "-q")
    git("add", "-A")
    git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "taste")
    monkeypatch.setattr(taste, "REPO", str(repo))
    monkeypatch.setattr(taste, "COMMIT", git("rev-parse", "HEAD"))
    monkeypatch.setattr(taste, "node_ready", lambda: True)
    return repo


def test_taste_skill_is_downloaded_once_as_a_plugin(upstream, tmp_path):
    said = []
    plugin = taste.ensure(tmp_path / "cache", said.append)

    assert (plugin / "skills" / "taste-skill" / "SKILL.md").is_file()
    assert (plugin / "skills" / "taste-skill" / "LICENSE.txt").read_text() == "MIT License"
    assert '"name": "taste-skills"' in (plugin / ".claude-plugin" / "plugin.json").read_text()
    assert not any(p.name.endswith(".download") for p in (tmp_path / "cache").iterdir())
    assert any("downloading" in text for text in said)

    said.clear()
    assert taste.ensure(tmp_path / "cache", said.append) == plugin and said == []  # the second time it is there


@pytest.mark.parametrize("missing", ["node", "git", "network"])
def test_without_what_it_needs_frontren_keeps_its_own(upstream, tmp_path, monkeypatch, missing):
    if missing == "node":
        monkeypatch.setattr(taste, "node_ready", lambda: False)
    elif missing == "git":
        monkeypatch.setattr(taste.shutil, "which", lambda name: None)
    else:
        monkeypatch.setattr(taste, "REPO", str(tmp_path / "nowhere"))
    said = []

    assert taste.ensure(tmp_path / "cache", said.append) is None
    assert "keeps its own design skills" in said[-1]
    assert not (tmp_path / "cache").exists() or not any((tmp_path / "cache").iterdir())


def test_frontren_designs_with_taste_skill_when_it_is_there(fake_claude, upstream, tmp_path):  # noqa: F811
    plugin = taste.ensure(tmp_path / "cache", lambda text: None)
    office = Office(tmp_path / "ws", design_plugin=plugin)
    office.start_task("Make a landing page", "frontend")
    office.wait_idle()

    call = work(fake_claude())[0]
    assert all_args(call, "--plugin-dir") == [str(SKILLS_DIR / "developer"), str(SKILLS_DIR / "frontend"), str(plugin)]
    prompt = arg(call, "--append-system-prompt")
    assert "design-taste-frontend for any new or reshaped interface" in prompt
    assert "visual-craft" not in prompt and "frontend-design" not in prompt and "motion when" not in prompt
    assert "design-taste-frontend" in {s["name"] for s in office.skills["frontend"]}


def test_without_taste_skill_frontren_has_its_classic_design_skills(fake_claude, tmp_path):  # noqa: F811
    office = Office(tmp_path / "ws")
    office.start_task("Make a landing page", "frontend")
    office.wait_idle()

    call = work(fake_claude())[0]
    assert all_args(call, "--plugin-dir")[-1] == str(SKILLS_DIR / "frontend-classic")
    assert "frontend-design for any new or reshaped interface" in arg(call, "--append-system-prompt")
    assert Office(tmp_path / "ws2", skills=False, design_plugin=tmp_path).design_skill is None
