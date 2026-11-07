---
name: debugging
description: Use when something fails, such as a test, a crash, wrong output or a bug from a review note. Finds the root cause before any code changes.
---

# Debugging

1. Reproduce first: find the smallest command or test that shows the failure, and run it.
2. Read the whole error and stack trace, and find the first frame in this project's own code.
3. Test one hypothesis at a time with a print, a log line or a debugger. Do not change code at random to see what happens.
4. Fix the cause, not the symptom. If `None` arrives where a value was expected, find where it came from instead of guarding the place it crashed.
5. Keep the reproduction as a regression test that fails without the fix.
6. Remove the temporary prints and logs.
7. In your final message, say what the cause was and which test proves the fix.
