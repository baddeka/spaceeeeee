---
name: frontend-verify
description: Use after building or changing a UI, before saying it is done. Runs the app and checks it in a real browser at desktop and phone sizes.
---

# Verify the frontend in a browser

Reading the code is not enough for a UI: run it and look.

1. Build and type-check first if the project has those steps (`npm run build`, `npx tsc --noEmit`, the linter). Fix every error.
2. Start the app or a static server (`npm run dev`, `python3 -m http.server 8000`) in the background and note the real port from its output.
3. If Playwright is available (`node -e "require('playwright')"` succeeds), write a short script outside the project that:
   - opens the page at 1440x900 and at 390x844,
   - collects console errors and failed requests,
   - checks `document.documentElement.scrollWidth <= innerWidth` (no horizontal scroll),
   - clicks through the main flow of the task,
   - saves a screenshot of each size.
   Look at the screenshots and fix what is wrong: overlapping text, cut-off content, unreadable contrast, broken layout.
4. Without Playwright, at least fetch the page with `curl` and check that it returns 200 and the expected markup, and say that a visual check was not possible.
5. Stop the servers you started.

In your final message, list the sizes you checked, console errors found (or none), and what you fixed.
