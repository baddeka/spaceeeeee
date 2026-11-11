"""frontren's design skill: Taste Skill, downloaded once at a pinned version.

Taste Skill (github.com/Leonxlnx/taste-skill, MIT) won the office's bake-off against frontren's own
design skills and UI/UX Pro Max: same task, same model, the most finished-looking page. It is 40 MB
of skill, photos, effects and Node scripts, too much to ship inside the office, so the office fetches
it into the user's cache the first time and reuses it after. Without git, a network or Node 22, the
office keeps frontren's own design skills instead.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = "https://github.com/Leonxlnx/taste-skill"
COMMIT = "f6b76575f949707b4e3c37cd86cb44b0b98643e8"  # 2026-11-07; a newer one is taken by changing this
SKILL_PATH = "skills/taste-skill"
SKILL_NAME = "design-taste-frontend"
NODE_MAJOR = 22
DOWNLOAD_SECONDS = 300


def cache_dir() -> Path:
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "rens-office"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "rens-office"


def plugin_dir(cache: Path | None = None) -> Path:
    return (cache or cache_dir()) / f"taste-skill-{COMMIT[:12]}"


def node_ready() -> bool:
    """Whether Node 22 or newer is there: the skill's scripts need it."""
    node = shutil.which("node")
    if node is None:
        return False
    try:
        version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    found = re.match(r"v(\d+)", version.strip())
    return bool(found) and int(found.group(1)) >= NODE_MAJOR


def ensure(cache: Path | None = None, say=lambda text: print(text, file=sys.stderr)) -> Path | None:
    """The Taste Skill plugin folder, downloaded if needed; None when it cannot be used here."""
    target = plugin_dir(cache)
    if (target / "skills" / "taste-skill" / "SKILL.md").is_file():
        return target if node_ready() else _without("Node 22 or newer is not installed", say)
    if not node_ready():
        return _without("Node 22 or newer is not installed", say)
    git = shutil.which("git")
    if git is None:
        return _without("git is not installed", say)
    say("Rens Office: downloading frontren's design skill (Taste Skill, about 40 MB, once)...")
    work = target.with_name(target.name + ".download")
    shutil.rmtree(work, ignore_errors=True)
    try:
        for args in (
            ["init", "-q", str(work / "repo")],
            ["-C", str(work / "repo"), "fetch", "-q", "--depth", "1", REPO, COMMIT],
            ["-C", str(work / "repo"), "checkout", "-q", "FETCH_HEAD"],
        ):
            subprocess.run([git, *args], check=True, capture_output=True, timeout=DOWNLOAD_SECONDS)
        plugin = work / "plugin"
        (plugin / ".claude-plugin").mkdir(parents=True)
        (plugin / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "taste-skills", "version": COMMIT[:12], "description": f"Taste Skill from {REPO}"}),
            encoding="utf-8",
        )
        (plugin / "skills").mkdir()
        shutil.move(str(work / "repo" / SKILL_PATH), str(plugin / "skills" / "taste-skill"))
        shutil.copy(work / "repo" / "LICENSE", plugin / "skills" / "taste-skill" / "LICENSE.txt")
        if not (plugin / "skills" / "taste-skill" / "SKILL.md").is_file():
            raise OSError("the downloaded repository has no skill where expected")
        shutil.rmtree(target, ignore_errors=True)
        shutil.move(str(plugin), str(target))
    except (OSError, subprocess.SubprocessError) as e:
        detail = getattr(e, "stderr", b"") or b""
        reason = detail.decode(errors="replace").strip().splitlines()[-1:] or [str(e)]
        return _without(f"the download failed ({reason[0][:160]})", say)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    say("Rens Office: frontren's design skill is ready.")
    return target


def _without(reason: str, say) -> None:
    say(f"Rens Office: frontren keeps its own design skills, since {reason}.")
    return None
