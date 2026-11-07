"""The projects: a folder each, kept in one projects folder, and the one the office has open."""

from __future__ import annotations

import json
import queue
import threading
from collections.abc import Callable
from pathlib import Path

from .agents import STATE_FILE, Busy, Office, safe_file_name
from .i18n import LANGUAGES, t

# Statuses in which an agent is doing something a project switch would cut short.
BUSY_STATUSES = {"working", "reviewing", "thinking"}


def default_projects_dir() -> Path:
    documents = Path.home() / "Documents"
    return (documents if documents.is_dir() else Path.home()) / "Rens Projects"


class Projects:
    """The project list and the one open project; the office works on one project at a time."""

    def __init__(self, root: Path, open_office: Callable[[Path, str], Office], lang: str = "en"):
        self.root = root
        self._open_office = open_office  # (folder, language) -> the office for that project
        self.lang = lang
        self.office: Office | None = None
        # The subscription limits are the account's, not a project's: they carry over a switch.
        self._limits: list[dict] | None = None
        self._lock = threading.RLock()
        # Pages showing the project list; they reload when a project opens.
        self._waiting: list[queue.Queue] = []

    def snapshot(self) -> dict:
        with self._lock:
            office = self.office
            limits = self._limits
        if office is not None:
            return office.snapshot()
        return {
            "project": None,
            "projects": self.list(),
            "projects_dir": str(self.root),
            "lang": self.lang,
            "limits": limits,
        }

    def list(self) -> list[dict]:
        """The projects in the projects folder, the most recently used first."""
        if not self.root.is_dir():
            return []
        found = [_describe(folder) for folder in self.root.iterdir() if folder.is_dir() and not folder.name.startswith(".")]
        return sorted(found, key=lambda project: project["updated"], reverse=True)

    def create(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError(t(self.lang, "empty_project_name"))
        folder = self.root / safe_file_name(name)
        if folder.exists():
            raise ValueError(t(self.lang, "project_exists", name=folder.name))
        self.open(folder)

    def open(self, folder: Path) -> None:
        folder = Path(folder).expanduser()
        if not folder.is_absolute():
            # A bare name is a project in the projects folder, never one where the server happens to run.
            folder = self.root / folder
        folder = folder.resolve()
        self._check_folder(folder)
        with self._lock:
            self._release(check_busy=True)
            office = self._open_office(folder, self.lang)
            if self._limits:
                office.limits = self._limits
            self.office = office
            waiting = list(self._waiting)
        if not office.limits:
            office.refresh_limits()
        for q in waiting:
            q.put({"type": "reload"})

    def close(self) -> None:
        """Back to the project list."""
        with self._lock:
            self._release(check_busy=True)

    def shutdown(self) -> None:
        with self._lock:
            self._release(check_busy=False)

    def set_language(self, lang: str) -> None:
        if lang not in LANGUAGES:
            raise ValueError(t(self.lang, "unknown_language"))
        with self._lock:
            self.lang = lang
            office = self.office
        if office is not None:
            office.set_language(lang)

    def wait_for_project(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._waiting.append(q)
        return q

    def stop_waiting(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._waiting:
                self._waiting.remove(q)

    def _release(self, check_busy: bool) -> None:
        office = self.office
        if office is None:
            return
        if check_busy and any(agent["status"] in BUSY_STATUSES for agent in office.snapshot()["agents"].values()):
            raise Busy(t(self.lang, "busy_switch"))
        self._limits = office.limits or self._limits
        office.close()
        self.office = None

    def _check_folder(self, folder: Path) -> None:
        # The office commits everything in a project, so a folder that holds far more than one
        # project (a drive, the home folder, the projects folder itself) must never become one.
        home = Path.home().resolve()
        if folder == Path(folder.anchor) or folder == home or folder in home.parents or folder == self.root.resolve():
            raise ValueError(t(self.lang, "unsafe_project", folder=str(folder)))
        if folder.exists() and not folder.is_dir():
            raise ValueError(t(self.lang, "not_a_folder", folder=str(folder)))


def _describe(folder: Path) -> dict:
    """A project as the list shows it: its name, when it was last used, and where it stands."""
    state = folder / STATE_FILE
    try:
        saved = json.loads(state.read_text(encoding="utf-8"))
        updated = state.stat().st_mtime
    except (OSError, ValueError):
        saved, updated = None, folder.stat().st_mtime
    saved = saved if isinstance(saved, dict) else {}
    history = [done for done in saved.get("history") or [] if isinstance(done, dict) and isinstance(done.get("title"), str)]
    task = saved.get("task_title")
    return {
        "name": folder.name,
        "path": str(folder),
        "updated": updated,
        "task": task if isinstance(task, str) else None,
        "done": len(history),
        "last_done": history[-1]["title"] if history else None,
    }
