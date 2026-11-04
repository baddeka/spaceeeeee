#!/usr/bin/env python3
"""Stand-in for the `claude` CLI in tests. Behaves like `claude -p --output-format stream-json`.

Reads FAKE_CLAUDE_LOG (where to append the received args), FAKE_CLAUDE_REVIEW (the review to
return when called with the review schema), FAKE_CLAUDE_IDEAS (the ideas to return when called
with the ideas schema), FAKE_CLAUDE_SKILL (a skill the worker loads), FAKE_CLAUDE_FAIL,
FAKE_CLAUDE_NOISE (bytes of stderr to write first) and FAKE_CLAUDE_HANG (a file to write the pid
of a child process to before waiting forever, like a worker running a server).
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

args = sys.argv[1:]
prompt = sys.stdin.read()

if log := os.environ.get("FAKE_CLAUDE_LOG"):
    with open(log, "a") as f:
        f.write(json.dumps({"args": args, "prompt": prompt}) + "\n")


def emit(event):
    print(json.dumps(event), flush=True)


def result(text, structured=None, cost=0.01):
    emit({"type": "result", "subtype": "success", "is_error": False, "result": text,
          "structured_output": structured, "session_id": session, "total_cost_usd": cost,
          "modelUsage": {"claude-test": {}}})


DEFAULT_IDEAS = {
    "ideas": [
        {"title": "Habit tracker CLI", "pitch": "Track daily habits from the terminal.",
         "why": "No account, works offline.", "scope": "small",
         "task": "Build habits.py: add, done, and streak commands, stored in a JSON file. Tests for each."},
        {"title": "Focus timer page", "pitch": "A one-page pomodoro timer.",
         "why": "No ads, works on phones.", "scope": "small",
         "task": "Build index.html with a 25/5 timer, start/pause/reset, and a sound at the end."},
        {"title": "Expense splitter", "pitch": "Split shared costs among friends.",
         "why": "Shows who owes whom in the fewest payments.", "scope": "medium",
         "task": "Build split.py that reads expenses.csv and prints the minimal set of payments."},
    ],
    "recommended": 1,
}

session = "sess-1"
if noise := os.environ.get("FAKE_CLAUDE_NOISE"):
    sys.stderr.write("w" * int(noise))  # more than a pipe holds, so nobody reading it would hang us
    sys.stderr.flush()
emit({"type": "system", "subtype": "init", "session_id": session})

if hang := os.environ.get("FAKE_CLAUDE_HANG"):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    Path(hang).write_text(str(child.pid))
    time.sleep(60)

if os.environ.get("FAKE_CLAUDE_FAIL"):
    print("boom", file=sys.stderr)
    sys.exit(1)

schema = args[args.index("--json-schema") + 1] if "--json-schema" in args else ""

if '"ideas"' in schema:
    ideas = json.loads(os.environ.get("FAKE_CLAUDE_IDEAS", json.dumps(DEFAULT_IDEAS)))
    emit({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Skill", "input": {"skill": "ideator-skills:brainstorm"}},
    ]}})
    result(json.dumps(ideas), ideas)
elif schema:
    review = json.loads(os.environ.get("FAKE_CLAUDE_REVIEW", '{"summary": "ok", "issues": []}'))
    emit({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Read", "input": {"file_path": "app.py"}},
    ]}})
    result(json.dumps(review), review)
else:
    if skill := os.environ.get("FAKE_CLAUDE_SKILL"):
        emit({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": f"worker-skills:{skill}"}},
        ]}})
    Path("app.py").write_text("print('hello')\n")
    emit({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Write", "input": {"file_path": str(Path.cwd() / "app.py")}},
        {"type": "text", "text": "Created app.py with a hello world."},
    ]}})
    result("Done: app.py prints hello. Run it with python3 app.py.", cost=0.02)
