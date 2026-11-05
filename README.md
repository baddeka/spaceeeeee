# Rens Office + ai-review

[Русская версия](README.ru.md)

Two tools built on Claude that run on a **Claude subscription (Pro or Max), with no API key**:

- **Rens Office** is a pixel-art web office with three agents: **idearen** proposes what to build on a topic you give, **coderen** writes the code, and **checkren** reviews it when you ask, or on its own with the autopilot, and sends it back for fixes.
- **ai-review** is a command-line reviewer: it checks a diff, gives a verdict of APPROVED or CHANGES REQUESTED, and sets the exit code for CI.

![Rens Office by day: idearen, coderen and checkren at their desks, ideas on a topic, and the log](docs/office.png)

## Install

You need Python 3.11+ and [Claude Code](https://code.claude.com), signed in with an account that has a subscription:

```bash
claude
```

```bash
pip install -e ".[dev]"
```

## Rens Office

```bash
ai-office --workspace ./my-project
```

Then open http://127.0.0.1:8000.

1. **Give task.** coderen, the developer, works in the `--workspace` folder: it creates and edits files and runs commands. Its speech bubble and the log show what it is doing right now.
2. **Call checkren.** checkren, the reviewer, looks at everything coderen changed since the task started, runs the checks from `.ai-review.toml`, and gives a verdict. It can read files but never change them.
3. **Send back.** The notes go to coderen, who continues the same conversation (`claude --resume`), so it remembers the task and its code.
4. **Accept.** The current state is committed to git, and the next task starts from it.

If the folder does not exist, it is created with a git repository. The office makes its own commits: `office: before task` before the first task and `office: accepted: …` when you accept.

### idearen, the idea maker

Write a topic under **Topic for idearen** and press **Get ideas**. idearen looks at the workspace, loads its skills and proposes 3 to 5 ideas, each with a pitch, why it is worth building, its scope (small, medium or large) and a complete brief for coderen. One is marked recommended.

**Give to coderen** hands an idea over as the next task, and a sticky note flies across the room. idearen only reads files and may use web search, so it can think while the others work. Asking again continues its conversation, so you get new ideas instead of the same ones.

### Autopilot

Turn on **Autopilot** and the loop runs by itself: new ideas send the recommended one to the developer when the office is free, the developer finishes, the reviewer is called, and rejected work goes back for fixes, up to the round limit you set. It stops when checkren approves, when the limit is reached, on an error, or when you press Stop. Accepting the work always stays with you. The **AUTO** sign above the door lights up while it runs.

### Day and night

The office follows your clock: dawn, day, evening and night, with the sky in the window and the light in the room. The **AUTO / DAY / NIGHT** switch in the header pins one of them.

An agent with nothing to do starts resting after a few seconds, each in its own way:

| Agent | When it rests |
|---|---|
| coderen | listens to music in its headphones, sips coffee, stretches, naps |
| checkren | reads a book, sips tea, stretches, naps |
| idearen | daydreams, juggles a ball, sips soda, stretches, naps |

At night the agents with nothing to do fall asleep: their screens go dark and Zs float up. Whoever has work keeps going by the light of the monitor and the desk lamp.

![Rens Office at night: checkren reviews under the desk lamp while coderen sleeps](docs/night.png)

### Skills

Each agent has its own skills: Claude Code skills, loaded only into that agent's runs as a plugin (`--plugin-dir`). Click an agent or its name plate to open its drawer with its skills, the skill in use, and its own activity.

![The developer's drawer: its skills and recent activity](docs/drawer.png)

| coderen (developer) | What it does |
|---|---|
| `test-first` | Writes tests for the behavior first, then code until they pass |
| `project-setup` | Sets up a new project: layout, dependencies, README, checks |
| `frontend-ui` | Builds pages and components: semantic, responsive, accessible, safe rendering |
| `frontend-verify` | Opens the app in a real browser at desktop and phone sizes |
| `address-review` | Works through review notes one by one, with regression tests |
| `self-check` | Runs the checks and rereads its own diff before handing off |

| checkren (reviewer) | What it does |
|---|---|
| `edge-cases` | Hunts for inputs that break the code |
| `test-review` | Checks whether the tests would catch a broken implementation |
| `security-review` | Looks for injection, path traversal, leaked secrets |
| `frontend-review` | Checks UI code: unsafe rendering, accessibility, layout, states |
| `verify-fixes` | On a re-review, checks that each earlier note is really fixed |

| idearen (idea maker) | What it does |
|---|---|
| `brainstorm` | Generates many raw ideas, then keeps a few distinct, buildable ones |
| `market-check` | Checks what already exists and finds what is missing |
| `write-brief` | Writes a brief the developer can build from without questions |

The skills live in `office/skills/<role>/skills/<name>/SKILL.md`. To add one, create a folder with a `SKILL.md` there; its `description` tells the agent when to use it. A label for the page in each language can go in `office/i18n.py` as `skill_<name>`.

### Files

Give the agents files along with a task or a topic: a design, a brief as a PDF, a data set, a logo. Use **📎 Attach files**, drop them onto the form, or paste a screenshot into the text box (up to 20 MB each). They are kept in the workspace's `.rens-office/uploads/`, which is never committed or reviewed, and the agent gets their paths and opens them with Read, which shows images and PDFs too. coderen copies into the project only what the project needs.

### Model and effort

Each agent's drawer has a **Model** list (Haiku, Sonnet, Opus, Fable) and an **Effort** list (`low` to `max`), so idearen can think on a cheap model while coderen builds on a strong one. A choice applies from the agent's next run and is kept in `~/.rens-office.json`. **auto** means `--model` or `--effort` from the command line, else Claude Code's default; checkren's effort on auto is the project's `effort`, else `high`. If Claude Code answers "You're out of usage credits", that model needs usage credits on your plan: pick another one.

### Projects

A project is the `--workspace` folder. Everything coderen makes stays there after the office stops, with its git history. To come back to a project, start the office with the same folder; for a new project, give it a new folder. Only these live while the office runs: coderen's conversation, the verdict, idearen's ideas and the log. After a restart coderen starts a new conversation and reads the files again.

Accept the work before you stop the office. The first task after a start commits everything in the folder as `office: before task`, so changes you had not accepted would no longer count as the change checkren reviews.

To work on an existing repository, such as your team's, point `--workspace` at your clone and switch to a branch of your own first. The office commits on the current branch under your git name (`user.name` and `user.email` in git's settings), or as "Rens Office" when git has none, and never pushes. Keep secrets such as `.env` in `.gitignore`: the office commits every file git does not ignore.

### Options

| Flag | What it does |
|---|---|
| `--workspace DIR` | project folder, default `./workspace` |
| `--port N` | port, default 8000 |
| `--host ADDR` | address to listen on, default `127.0.0.1` |
| `--allow-host NAME` | another name the page may be opened by, such as a Tailscale name (repeatable) |
| `--lang en\|ru` | language of the page and the agents, default `en`; the page also has an EN/RU switch |
| `--model M` | model for the agents left on auto in their drawer, for example `opus` or `claude-haiku-5-5` |
| `--effort` | `low` / `medium` / `high` / `xhigh` / `max`, for the agents left on auto |
| `--no-bash` | do not let the developer run shell commands; checks from `.ai-review.toml` are skipped too, since the developer can edit that file |
| `--no-skills` | run the agents without the office's skills |

**Safety.** The developer can run commands on your computer; `--no-bash` turns that off. The idea maker may read web pages, so its briefs are untrusted text: each brief tells the developer to stay in the project folder and not to download, install or send anything, but that is an instruction, not a sandbox. With the autopilot on, a brief reaches the developer before you read it; use `--no-bash` or keep the autopilot off when that matters. Because the developer can run commands, the server listens only on `127.0.0.1` and rejects requests from other sites: it checks `Host` and `Origin` and accepts only JSON. The page opens only by `localhost`, by the address given to `--host`, or by a name given to `--allow-host`; any other name is refused, so a site that points its own domain at your computer gets nothing. Do not expose it to a network unless you need to.

**Limits.** Each task and each review uses your subscription limits. The bars in the header show how much of the 5-hour and the weekly limit is used, as Claude Code reports it. To fill them at start, the office makes one tiny request to the smallest model (about 1,500 tokens); after that every agent run updates them, and a click on them checks again. Hover over a bar to see when it resets. `/usage` in Claude Code shows the same. The dollar amount next to them is Claude Code's estimate, not a charge.

### How the office saves your limits

- **Failing checks skip the model review.** If the project's checks fail, the work goes back with their output right away, without a reviewer run: the code will change anyway. Turn this off with `fast_fail = false` in `.ai-review.toml`.
- **New files are sent once.** Their content is already in the diff, so it is not repeated in the review prompt.
- **A re-review gets the previous notes** and coderen's reply to them, and checks each one instead of starting from scratch.
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
  processes.py    ends a command together with everything it started
  cli.py          the ai-review command
office/
  agents.py       the office: idea maker, developer, reviewer, autopilot, skills, git snapshots
  ideator.py      the idea maker's prompt and the schema of its ideas
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
