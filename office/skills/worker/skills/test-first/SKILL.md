---
name: test-first
description: Use when implementing or changing behavior. Write or update tests that pin the behavior, run them, and iterate until they pass.
---

# Test first

1. Find how the project runs tests: `.ai-review.toml` checks, `pyproject.toml`, `package.json` scripts, `Makefile`. If there are no tests yet, pick the standard runner for the language (pytest for Python, `node --test` or the existing runner for JavaScript) and add it to the dependency file.
2. Before writing the implementation, write tests for the behavior the task asks for:
   - the normal case,
   - at least one edge case (empty input, boundary value, missing file, invalid input),
   - the error behavior, if the task implies one.
3. Implement until the tests pass. Run the real test command; do not assume it passes.
4. If a test fails, read the failure and fix the code, not the assertion, unless the test itself is wrong.
5. Keep tests fast and independent: no network, no reliance on test order, temporary directories for files.

In your final message, name the test command and say how many tests ran and passed.
