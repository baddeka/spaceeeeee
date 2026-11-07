---
name: self-check
description: Use right before you say the work is done. A checklist that catches what the reviewer would otherwise send back.
---

# Self-check before handoff

Go through this list and fix anything it finds before your final message:

1. Run every command in `.ai-review.toml` `checks`, plus the test command. All must pass.
2. Read your own diff with `git diff` and `git status`:
   - no leftover debug prints, commented-out code, or TODOs you could finish now,
   - no unrelated files changed, no generated files or secrets added,
   - new files are not missing from the change.
3. Check the edges of every function you wrote: empty input, `None` or missing values, very large input, wrong types from callers.
4. Errors reach the user as clear messages, not raw stack traces.
5. The README or usage text matches what the code actually does.

In your final message, state which checks you ran and their results.
