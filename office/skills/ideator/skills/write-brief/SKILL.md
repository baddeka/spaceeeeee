---
name: write-brief
description: Use for every idea's task field. How to write a brief the developer can build from without asking questions.
---

# Write a brief for the developer

Write the `task` of each idea in this shape, in plain sentences:

1. **Goal:** one sentence on what to build and for whom.
2. **Features:** 3 to 6 bullet points, in the order to build them. The first one alone must already be useful.
3. **Acceptance criteria:** checkable statements, for example "running `python wc.py notes.txt` prints the word count" or "the page works at 375px wide with no horizontal scroll".
4. **Out of scope:** what not to build now (accounts, payments, deployment, and anything else that would double the work).
5. **Stack:** the language and libraries, matching the existing project if there is one. Prefer the standard library and plain HTML, CSS and JavaScript unless the idea really needs more.
6. **Tests:** what the tests should cover.

Rules:
- Be specific: name the files, commands, inputs and outputs when you can.
- No secrets, paid APIs or accounts unless the user asked for them; offer a local or mock version instead.
- Keep it under about 200 words; the developer has its own skills for the details.
