---
name: design-directions
description: Use when asked to propose style directions for an interface. How to find references and turn them into three distinct looks the user can choose from.
---

# Propose style directions

The user picks the style; your job is to give them three real choices, each concrete enough to build from.

## Look first
1. **What the user gave.** Open every attached file with Read. Screenshots from Pinterest, Dribbble or anywhere else show what they like: name what they share (color, density, type, mood) before searching.
2. **Figma.** With a figma.com link and the Figma tools, read the frames and their variables; a direction that matches the user's own design beats any reference.
3. **The project.** An existing `DESIGN.md`, stylesheet or component library is a constraint unless the user asks for a new look.
4. **References.** About three searches, for example `site:dribbble.com pomodoro timer app`, `site:land-book.com productivity landing`, `site:mobbin.com timer`, `pinterest calm study app ui`. Pinterest pages often block reading, so use what the search result itself says. Keep only references you saw: the link must come from a search result or a page you opened.

## Make three directions that really differ
- Vary the mood first (for example calm and paper-like, bold and playful, sharp and technical), then the palette and the type to match it. Three shades of the same idea are one direction.
- Fit the product and its people: a study timer for teenagers and a dashboard for accountants want different things.
- Recommend the one you would build, and say why in `fits`.

## For each direction
- **Palette:** 4 to 6 colors with roles: background, surface, text, muted text, accent, and one for success or danger when the interface needs it. Text on its background must reach a contrast of at least 4.5:1, the accent on its background 3:1. Give each as `#rrggbb`.
- **Fonts:** a heading and a body family that exist on Google Fonts. When the interface is in Russian, both must have Cyrillic (for example Inter, Manrope, Rubik, Unbounded, PT Serif, Montserrat, Onest).
- **Shapes:** corner radius, borders, shadows, spacing scale and density, in one or two sentences.
- **Components:** what buttons, inputs, cards, icons (prefer an icon set such as Lucide) and images look like.
- **References:** up to four, each with what to take from it.

Write everything in the language the user asked for, except the font names and colors.
