---
name: edge-cases
description: Use for any change with functions that take input. A systematic hunt for inputs that break the code.
---

# Edge cases

For each function or entry point the change adds or modifies, try these inputs in your head and trace what happens:

- **Empty:** empty string, list, dict, file; zero; no arguments.
- **Missing:** `None`/`null`/`undefined`, missing keys, missing files, missing environment variables.
- **Boundaries:** first and last element, off-by-one ranges, maximum sizes, negative numbers, very large numbers.
- **Types:** a string where a number is expected, an iterator where a list is expected, bytes versus text.
- **Text:** non-ASCII and emoji, very long lines, Windows line endings, leading and trailing whitespace.
- **Failure:** the network, disk, or subprocess fails or is slow; partial writes; the same operation run twice.

Report an edge case only when a realistic caller can hit it, and say which input triggers it and what goes wrong.
