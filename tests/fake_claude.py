#!/usr/bin/env python3
"""Stand-in for the `claude` CLI in tests. Behaves like `claude -p --output-format stream-json`.

Reads FAKE_CLAUDE_LOG (where to append the received args) and FAKE_CLAUDE_REVIEW
(the structured review to return when called with --json-schema).
"""

import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
prompt = sys.stdin.read()

if log := os.environ.get("FAKE_CLAUDE_LOG"):
    with open(log, "a") as f:
        f.write(json.dumps({"args": args, "prompt": prompt}) + "\n")


def emit(event):
    print(json.dumps(event), flush=True)


session = "sess-1"
emit({"type": "system", "subtype": "init", "session_id": session})

if os.environ.get("FAKE_CLAUDE_FAIL"):
    print("boom", file=sys.stderr)
    sys.exit(1)

if "--json-schema" in args:
    review = json.loads(os.environ.get("FAKE_CLAUDE_REVIEW", '{"summary": "ok", "issues": []}'))
    emit({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Read", "input": {"file_path": "app.py"}},
    ]}})
    emit({"type": "result", "subtype": "success", "is_error": False, "result": json.dumps(review),
          "structured_output": review, "session_id": session, "total_cost_usd": 0.01,
          "modelUsage": {"claude-test": {}}})
else:
    Path("app.py").write_text("print('hello')\n")
    emit({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Write", "input": {"file_path": str(Path.cwd() / "app.py")}},
        {"type": "text", "text": "Готово: создал app.py"},
    ]}})
    emit({"type": "result", "subtype": "success", "is_error": False, "result": "Создал app.py.",
          "session_id": session, "total_cost_usd": 0.02, "modelUsage": {"claude-test": {}}})
