#!/usr/bin/env python3
"""Stand-in for the `claude` CLI in tests. Behaves like `claude -p --output-format stream-json`.

Reads FAKE_CLAUDE_LOG (where to append the received args), FAKE_CLAUDE_REVIEW (the review to
return when called with the review schema), FAKE_CLAUDE_IDEAS (the ideas to return when called
with the ideas schema), FAKE_CLAUDE_STYLES (the style directions), FAKE_CLAUDE_SKILL (a skill the developer loads), FAKE_CLAUDE_FAIL,
FAKE_CLAUDE_NOISE (bytes of stderr to write first), FAKE_CLAUDE_HANG (a file to write the pid
of a child process to before waiting forever, like a developer running a server) and
FAKE_CLAUDE_RATE_LIMIT (the rate_limit_info of a rate_limit_event to report).
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
         "why": "No account, works offline.", "scope": "small", "developer": "backend", "ui": "",
         "task": "Build habits.py: add, done, and streak commands, stored in a JSON file. Tests for each."},
        {"title": "Focus timer page", "pitch": "A one-page pomodoro timer.",
         "why": "No ads, works on phones.", "scope": "small", "developer": "frontend",
         "ui": "One screen: a big countdown ring. Mood: calm, focused, paper-like. Phone first.",
         "task": "Build index.html with a 25/5 timer, start/pause/reset, and a sound at the end."},
        {"title": "Expense splitter", "pitch": "Split shared costs among friends.",
         "why": "Shows who owes whom in the fewest payments.", "scope": "medium", "developer": "backend", "ui": "",
         "task": "Build split.py that reads expenses.csv and prints the minimal set of payments."},
    ],
    "recommended": 1,
}

DEFAULT_STYLES = {
    "directions": [
        {"name": "Calm Paper", "mood": "calm, warm, focused", "summary": "Off-white paper and soft ink.",
         "palette": [{"role": "background", "hex": "#f7f3ea"}, {"role": "text", "hex": "#2b2433"},
                     {"role": "accent | links", "hex": "#e0508a"}, {"role": "muted text", "hex": "#75695a"}],
         "heading_font": "Unbounded", "body_font": "Onest", "shapes": "Soft 12px corners, no shadows.",
         "components": "Pill buttons and Lucide icons.",
         "references": [{"title": "Dribbble: focus timer", "url": "https://dribbble.com/shots/1-focus-timer",
                         "take": "the big ring"},
                        {"title": "A trap", "url": "javascript:alert(1)", "take": "nothing"}],
         "fits": "Students revise for hours; a quiet page keeps them in the flow."},
        {"name": "Arcade Night", "mood": "loud, playful, bright", "summary": "Neon on near-black.",
         "palette": [{"role": "background", "hex": "#0b1430"}, {"role": "text", "hex": "#f4f1ea"},
                     {"role": "accent", "hex": "red"}, {"role": "highlight", "hex": "#ffe066"}],
         "heading_font": "Press Start 2P", "body_font": "Rubik", "shapes": "Square corners, hard shadows.",
         "components": "Chunky buttons.", "references": [], "fits": "Makes a break feel like a game."},
        {"name": "Swiss Grid", "mood": "sharp, clear, technical", "summary": "A strict grid and one red.",
         "palette": [{"role": "background", "hex": "#ffffff"}, {"role": "text", "hex": "#111111"},
                     {"role": "accent", "hex": "#d62828"}],
         "heading_font": "Manrope", "body_font": "Inter", "shapes": "No corners, thin rules.",
         "components": "Text buttons.", "references": [], "fits": "Shows the time and nothing else."},
    ],
    "recommended": 0,
}

session = "sess-1"
if noise := os.environ.get("FAKE_CLAUDE_NOISE"):
    sys.stderr.write("w" * int(noise))  # more than a pipe holds, so nobody reading it would hang us
    sys.stderr.flush()
emit({"type": "system", "subtype": "init", "session_id": session})
if limits := os.environ.get("FAKE_CLAUDE_RATE_LIMIT"):
    emit({"type": "rate_limit_event", "rate_limit_info": json.loads(limits)})

if hang := os.environ.get("FAKE_CLAUDE_HANG"):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    Path(hang).write_text(str(child.pid))
    time.sleep(60)

if os.environ.get("FAKE_CLAUDE_FAIL"):
    print("boom", file=sys.stderr)
    sys.exit(1)

schema = args[args.index("--json-schema") + 1] if "--json-schema" in args else ""

if '"directions"' in schema:
    styles = json.loads(os.environ.get("FAKE_CLAUDE_STYLES", json.dumps(DEFAULT_STYLES)))
    emit({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "WebSearch", "input": {"query": "site:dribbble.com focus timer"}},
    ]}})
    result(json.dumps(styles), styles)
elif '"ideas"' in schema:
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
elif args[args.index("--tools") + 1] == "":
    result(".", cost=0.0003)  # a run without tools only answers, like the limits check
else:
    if skill := os.environ.get("FAKE_CLAUDE_SKILL"):
        emit({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": f"developer-skills:{skill}"}},
        ]}})
    Path("app.py").write_text("print('hello')\n")
    emit({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Write", "input": {"file_path": str(Path.cwd() / "app.py")}},
        {"type": "text", "text": "Created app.py with a hello world."},
    ]}})
    result("Done: app.py prints hello. Run it with python3 app.py.", cost=0.02)
