---
name: frontend-ui
description: Use when building or changing a web page, component, or UI (HTML, CSS, JavaScript, TypeScript, React, Vue, Svelte). Standards for structure, layout, accessibility, UI states, and safe rendering.
---

# Frontend UI

Follow the project's existing framework and styles. Without one, plain HTML, CSS and JavaScript are fine; do not add a framework for a small page.

## Structure and safety
- Use semantic elements: `button` for actions, `a` for navigation, `label` for every input, headings in order.
- Never put user or server data into `innerHTML`, `dangerouslySetInnerHTML`, or `v-html`. Set `textContent` or let the framework escape it.
- Keep API URLs and keys out of the bundle; secrets belong on the server.

## Layout
- Mobile first. The page must work at 375px wide with no horizontal scroll, and at 1440px without stretching text across the screen (cap line length near 70 characters).
- Use flexbox or grid with `gap`, not fixed pixel widths or absolute positioning for layout.
- Images get `width`/`height` or `aspect-ratio` so the page does not jump while loading.

## Styles
- Put colors, spacing and fonts in CSS variables on `:root`. Support dark mode with `prefers-color-scheme` when the project has no theme system.
- Text contrast at least 4.5:1. Never remove focus outlines without a visible replacement.
- Respect `prefers-reduced-motion` for animations.

## States
Every view that loads or submits data needs four states: loading, empty, error (with a retry or a clear next step), and success. Disable a submit button while its request runs so a double click cannot send twice.

## Accessibility
- Everything clickable works with the keyboard (Tab, Enter, Space, Esc for dialogs).
- Images have `alt` text; icon-only buttons have `aria-label`.
- Dialogs and drawers move focus inside when they open and return it when they close.
