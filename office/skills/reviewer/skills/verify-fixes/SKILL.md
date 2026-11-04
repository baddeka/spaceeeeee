---
name: verify-fixes
description: Use when the prompt lists notes from a previous review. Checks each earlier note is really fixed and the fixes did not break anything else.
---

# Verify fixes

1. Go through the previous notes one by one. For each, find the code that addresses it and decide:
   - fixed: the root cause is gone, ideally with a regression test,
   - partly fixed: the reported input works but a closely related input still fails,
   - not fixed: the problem is still there.
2. Report every partly fixed or not fixed note again, with the same severity or higher, and say what is still wrong.
3. Look for regressions the fixes introduced: changed behavior elsewhere, deleted or weakened tests, new edge cases.
4. Do not re-raise a note the developer explained convincingly; mention in the summary that you accept the explanation.
5. Start the summary with how many previous notes are fixed, for example "3 of 4 earlier notes are fixed."
