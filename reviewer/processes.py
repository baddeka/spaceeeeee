"""Ending a command together with everything it started."""

from __future__ import annotations

import os
import signal
import subprocess


def kill_tree(proc: subprocess.Popen, force: bool = False) -> None:
    """Ends `proc`, started with `start_new_session=True`, and every process it started.

    Killing only the process itself would leave its children running: a test server keeps
    its port, a build keeps the CPU busy.
    """
    if os.name == "nt":
        # Windows has no process groups; taskkill follows the tree from the parent instead.
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False)
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL if force else signal.SIGTERM)
    except ProcessLookupError:
        pass  # everything in the group has already exited
