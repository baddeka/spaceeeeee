---
name: project-setup
description: Use when the workspace is empty or the task starts a new project or component. Sets up a conventional layout, dependencies, and run instructions.
---

# Project setup

Set up only what the task needs; do not scaffold a framework nobody asked for.

1. Look at what already exists (`ls`, existing config files) and follow its conventions.
2. For a new project, create:
   - source code in a conventional place for the language (a package directory for Python, `src/` for TypeScript),
   - a dependency file with pinned or bounded versions (`pyproject.toml` or `requirements.txt`, `package.json`),
   - a `.gitignore` for the language (virtualenvs, `node_modules`, caches, build output),
   - a short `README.md`: what it does, how to install, how to run, how to test.
3. Add an `.ai-review.toml` with the project's test and lint commands, so the reviewer runs them:

   ```toml
   checks = ["python -m pytest -q"]
   ```

4. Never commit secrets. Read configuration from environment variables and document them in the README.
