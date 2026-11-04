# AI Office + ai-review

[Русская версия](README.ru.md)

Two tools built on Claude that run on a **Claude subscription (Pro or Max), with no API key**:

- **AI Office** is a pixel-art web office with two agents. The developer writes code for your task; the reviewer checks it when you ask, or on its own with the autopilot, and sends it back for fixes.
- **ai-review** is a command-line reviewer: it checks a diff, gives a verdict of APPROVED or CHANGES REQUESTED, and sets the exit code for CI.

![AI Office: the developer and the reviewer at their desks, a verdict with two notes, and the log](docs/office.png)

## Install

You need Python 3.11+ and [Claude Code](https://code.claude.com), signed in with an account that has a subscription:

```bash
claude
```

```bash
pip install -e ".[dev]"
```

## AI Office

```bash
ai-office --workspace ./my-project
```

Then open http://127.0.0.1:8000.

1. **Give task.** The developer works in the `--workspace` folder: it creates and edits files and runs commands. Its speech bubble and the log show what it is doing right now.
2. **Call reviewer.** The reviewer looks at everything the developer changed since the task started, runs the checks from `.ai-review.toml`, and gives a verdict. It can read files but never change them.
3. **Send back.** The notes go to the developer, who continues the same conversation (`claude --resume`), so it remembers the task and its code.
4. **Accept.** The current state is committed to git, and the next task starts from it.

If the folder does not exist, it is created with a git repository. The office makes its own commits: `office: before task` before the first task and `office: accepted: …` when you accept.

### Autopilot

Turn on **Autopilot** and the loop runs by itself: the developer finishes, the reviewer is called, and rejected work goes back for fixes, up to the round limit you set. It stops when the reviewer approves, when the limit is reached, on an error, or when you press Stop. Accepting the work always stays with you. The **AUTO** sign above the door lights up while it runs.

### Skills

Each agent has its own skills: Claude Code skills, loaded only into that agent's runs as a plugin (`--plugin-dir`). Click an agent or its name plate to open its drawer with its skills, the skill in use, and its own activity.

![The developer's drawer: its skills and recent activity](docs/drawer.png)

| Developer | What it does |
|---|---|
| `test-first` | Writes tests for the behavior first, then code until they pass |
| `project-setup` | Sets up a new project: layout, dependencies, README, checks |
| `frontend-ui` | Builds pages and components: semantic, responsive, accessible, safe rendering |
| `frontend-verify` | Opens the app in a real browser at desktop and phone sizes |
| `address-review` | Works through review notes one by one, with regression tests |
| `self-check` | Runs the checks and rereads its own diff before handing off |

| Reviewer | What it does |
|---|---|
| `edge-cases` | Hunts for inputs that break the code |
| `test-review` | Checks whether the tests would catch a broken implementation |
| `security-review` | Looks for injection, path traversal, leaked secrets |
| `frontend-review` | Checks UI code: unsafe rendering, accessibility, layout, states |
| `verify-fixes` | On a re-review, checks that each earlier note is really fixed |

The skills live in `office/skills/<role>/skills/<name>/SKILL.md`. To add one, create a folder with a `SKILL.md` there; its `description` tells the agent when to use it. A label for the page in each language can go in `office/i18n.py` as `skill_<name>`.

### Options

| Flag | What it does |
|---|---|
| `--workspace DIR` | project folder, default `./workspace` |
| `--port N` | port, default 8000 |
| `--lang en\|ru` | language of the page and the agents, default `en`; the page also has an EN/RU switch |
| `--model M` | model for both agents, for example `opus` or `claude-haiku-5-5` |
| `--effort` | `low` / `medium` / `high` / `xhigh` / `max` |
| `--no-bash` | do not let the developer run shell commands |
| `--no-skills` | run the agents without the office's skills |

**Safety.** The developer can run commands on your computer; `--no-bash` turns that off. That is why the server listens only on `127.0.0.1` and rejects requests from other sites: it checks `Host` and `Origin` and accepts only JSON. Do not expose it to a network unless you need to.

**Limits.** Each task and each review uses your subscription limits. The dollar amount in the header is Claude Code's estimate, not a charge.

### How the office saves your limits

- **Failing checks skip the model review.** If the project's checks fail, the work goes back with their output right away, without a reviewer run: the code will change anyway. Turn this off with `fast_fail = false` in `.ai-review.toml`.
- **New files are sent once.** Their content is already in the diff, so it is not repeated in the review prompt.
- **A re-review gets the previous notes** and checks each one, instead of starting from scratch.
- **Caches stay out.** `__pycache__`, `node_modules`, virtualenvs and the like go into the repository's local exclude file, so they are never reviewed or committed.
- The reviewer starts fresh for each review and only reads files; the developer keeps one conversation, so fixes do not repeat context.

## ai-review

```bash
ai-review --check "pytest -q"
```

```bash
ai-review --base main
```

```bash
ai-review --files src/api.py
```

The code makes the verdict, not the model: a change is not approved if any check fails or there is a `critical` or `major` note. `minor` and `nit` notes are shown but do not block.

| Flag | What it does |
|---|---|
| `--base REF` | review the diff from the merge base with a branch or commit |
| `--files ...` | review whole files instead of a diff |
| `--check CMD` | a check command; can be given several times |
| `--no-checks` | skip the checks from `.ai-review.toml` |
| `--backend` | `claude-code` (default, uses your subscription) or `api` (uses `ANTHROPIC_API_KEY`) |
| `--model`, `--effort` | model and reasoning depth |
| `--json` | print JSON |

Exit codes: `0` approved, `1` changes requested, `2` error.

- **`claude-code`** runs `claude -p` with a JSON schema for the answer and read-only tools (`Read`, `Grep`, `Glob`), so the reviewer can open other files, such as callers or tests. It needs Claude Code to be signed in; for CI there is the token from `claude setup-token`.
- **`api`** uses the Claude API (`claude-opus-5-5`) with structured output and server-side fallback. It needs `ANTHROPIC_API_KEY`.

## Project settings

Both tools read `.ai-review.toml` in the project root:

```toml
checks = ["pytest -q", "ruff check ."]
effort = "high"
fast_fail = true
instructions = """
We use FastAPI. Every endpoint validates its input with pydantic.
"""
```

## How it is built

```
reviewer/
  context.py      collects the diff and changed files, runs the checks
  llm.py          reviewer prompt, answer schema, verdict, the api and claude-code backends
  claude_code.py  runs `claude -p` and streams its stream-json events
  cli.py          the ai-review command
office/
  agents.py       the office: developer, reviewer, autopilot, skills, git snapshots
  i18n.py         English and Russian texts of the office
  server.py       HTTP server and the event stream (SSE) for the page
  skills/         each agent's skills as a Claude Code plugin
  static/         the page: scene.js draws the pixel office, app.js runs the interface
```

## Tests

```bash
python -m pytest -q
```

The tests call neither the API nor Claude Code: `tests/fake_claude.py` stands in for `claude`.
