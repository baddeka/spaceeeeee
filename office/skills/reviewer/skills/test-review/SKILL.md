---
name: test-review
description: Use when the change adds or modifies tests, or when behavior changes without tests. Judges whether the tests would actually catch a broken implementation.
---

# Test review

1. For each behavior the change introduces, find the test that covers it. A behavior with no test is a finding: major when it is the main purpose of the change, minor otherwise.
2. For each test, ask: if the implementation were wrong, would this test fail? Flag tests that:
   - assert only that no exception was raised, or only the type of the result,
   - mock the very function they claim to test,
   - compare a value with itself or with output computed by the same code,
   - depend on test order, wall-clock time, randomness without a seed, or the network.
3. Check that edge cases from the task have tests: empty input, boundaries, invalid input, error paths.
4. Read the check results: a failing or skipped test caused by the change is at least major.
