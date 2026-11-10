---
name: ui-kit
description: Use at the start of any interface, before writing markup. Which ready-made components, icons, pictures and charts to use so nothing is drawn from scratch.
---

# Use what exists

Hand-drawn icons, home-made dropdowns and grey boxes instead of pictures are what make a page look generated. They also cost the most to write. Pick from the shelf first.

## Components
- **The project already has a kit or its own components:** use them. Never add a second kit.
- **React with Tailwind:** shadcn/ui. Add only the components you use, and theme them through its CSS variables from `DESIGN.md`.
- **Tailwind without React, or plain HTML that may load a stylesheet:** daisyUI, themed with its color variables.
- **A small plain page:** no kit. Write the few components yourself on native elements: `button`, `dialog`, `details`, `input`, `select`. Native elements already handle keyboard and focus.
- Check the kit's own documentation for the current install snippet before you paste one from memory.

A kit gives behavior and structure. The look still comes from `DESIGN.md`: restyle its colors, radius, fonts and spacing, or the page looks like every other page built with that kit.

## Icons
One icon set for the whole page; Lucide is the default (as an npm package, or its script from a CDN with `data-lucide` attributes). Same stroke width and size everywhere. Never draw an icon by hand and never use emoji as interface icons.

## Pictures
- The user's own images first: copy what you need from the files they attached.
- Photos as stand-ins: `https://picsum.photos/seed/<word>/<width>/<height>` gives a stable photo per word. Say in your final message which pictures are stand-ins.
- People: initials on a colored circle, not a stock face.
- Every image gets `width` and `height` (or `aspect-ratio`), `alt`, and `loading="lazy"` below the first screen.
- No picture is better than a wrong one: a strong type treatment or a solid color block often serves better than a decorative photo.

## Charts and data
Chart.js for ordinary charts; plain SVG for one simple sparkline or bar. Use realistic numbers, with units.

## Fonts
The two families in `DESIGN.md`, from Google Fonts, with `display=swap` and only the weights you use. A system font stack as the fallback.

## Before adding anything
Each dependency must earn its place: if a few lines of CSS do the job, write them. Load nothing that needs an account or a key unless the user asked for it.
