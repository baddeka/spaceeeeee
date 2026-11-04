import subprocess
from contextlib import contextmanager
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
