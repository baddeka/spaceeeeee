---
name: frontend-review
description: Use when the change touches HTML, CSS, JavaScript, TypeScript, or UI components. A checklist of frontend defects: unsafe rendering, accessibility, layout, UI states, and performance.
---

# Frontend review

Look for these, and report each with the element or component and the user action that triggers it.

## Safety
- User or server data rendered through `innerHTML`, `insertAdjacentHTML`, `document.write`, `dangerouslySetInnerHTML`, or `v-html`: critical when the data can contain markup.
- API keys or secrets in frontend code or committed `.env` files that the bundle reads.
- Links that open new tabs to external sites without `rel="noopener"`.

## Accessibility
- Clickable `div`/`span` instead of `button` or `a`; controls that do not work with the keyboard.
- Inputs without a `label`; icon buttons without `aria-label`; images without `alt`.
- Focus outlines removed with nothing visible instead; dialogs that do not trap or restore focus.
- Text contrast below 4.5:1.

## Layout
- Fixed widths or absolute positioning that break at 375px wide or cause horizontal scroll.
- Text that can overflow its container (long words, long translations) with no wrapping or truncation.

## States and behavior
- Missing loading, empty, or error states for data that is fetched.
- Errors from requests ignored, so the UI hangs or shows stale data.
- Double submit possible; race conditions where a slow old response overwrites a newer one.

## Performance
- Work repeated on every render or every scroll event without throttling; listeners or timers never removed.
- Large images or libraries loaded for a small feature.
