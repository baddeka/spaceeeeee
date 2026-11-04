import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest


def git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test")
    return tmp_path


class FakeClient:
    """Stands in for anthropic.Anthropic and records the request it receives."""

    def __init__(self, parsed_output=None, stop_reason="end_turn", model="claude-opus-5-5"):
        self.message = SimpleNamespace(
            parsed_output=parsed_output, stop_reason=stop_reason, model=model
        )
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    @contextmanager
    def _stream(self, **kwargs):
        self.requests.append(kwargs)
        yield SimpleNamespace(get_final_message=lambda: self.message)


def process_gone(pid, timeout=5.0):
    """Waits until a process has exited; True when it did within the timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        # A killed child stays a zombie until something reaps it; for these tests it is gone.
        try:
            state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[-1].split()[0]
        except (FileNotFoundError, ProcessLookupError):
            state = None  # reaped just now (the next check sees it), or a system without /proc
        if state == "Z":
            return True
        time.sleep(0.05)
    return False


def wait_for_file(path, timeout=10.0):
    """Waits until a file has content: it exists, empty, for a moment before it is written."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists() and (text := path.read_text()):
            return text
        time.sleep(0.05)
    return path.read_text()
