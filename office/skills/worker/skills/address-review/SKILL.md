---
name: address-review
description: Use when you receive review notes from the reviewer. Works through each note, fixes root causes, and reports what changed per note.
---

# Address review notes

1. Read every note before changing anything. Group notes that share a root cause.
2. Fix in order of severity: critical, major, then minor; nits only when the fix is trivial.
3. For each bug-type note:
   - reproduce it first with a test that fails,
   - fix the root cause, not just the reported input,
   - keep the test as a regression test.
4. If you disagree with a note, do not silently skip it. Explain in your reply why the current behavior is correct, with the concrete input that proves it.
5. Re-run the full test command after all fixes, not just the new tests.
6. Reply with one line per note: its title, then "fixed: <what changed>" or "not changed: <why>".
