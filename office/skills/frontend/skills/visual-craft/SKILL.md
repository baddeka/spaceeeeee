---
name: visual-craft
description: Use for every interface, while laying it out and styling it. The concrete rules of spacing, type, color and hierarchy that make a page look designed rather than assembled.
---

# Visual craft

`DESIGN.md` says which colors, fonts and shapes. This says how to use them well. Most pages that look wrong break one of these rules.

## Hierarchy: decide what leads
On every screen, name the one thing a visitor must see first and the one action they should take. Make that thing clearly the biggest or the boldest, and that action the only filled button. Everything else is a step quieter. If three things shout, nothing leads.

Three levels are enough: primary (the headline, the main action), secondary (section titles, supporting text), tertiary (labels, meta, captions). Build the levels with size, weight and color together, not with size alone.

## Spacing: one scale, used strictly
Use a scale and nothing off it: 4, 8, 12, 16, 24, 32, 48, 64, 96 px. Put it in CSS variables.
- Things that belong together sit close (8 to 16); groups sit apart (32 to 64). The gap between groups is at least twice the gap inside them. This, more than any border, shows what belongs to what.
- Be generous. Cramped is the commonest flaw: when unsure, take the next step up.
- Padding inside a box is at least as large as the gap between its items.
- Same kind of thing, same spacing, everywhere.

## Type
- A scale with real contrast: body 16 to 18 px, then steps of about 1.25 to 1.33; a page headline of 40 to 72 px on desktop and 32 to 44 on a phone. A headline only a little bigger than body text looks timid.
- Line height: about 1.5 for body, 1.1 to 1.2 for large headlines. Tighten letter spacing slightly on big headings; open it on small capitals.
- Line length 45 to 75 characters: set `max-width` in `ch` on text blocks.
- Two weights are usually enough: regular and one strong one. Muted text is a color, not a thinner weight.
- Left-align text. Center only short headlines and single lines.

## Color
- Spread it roughly 60, 30, 10: background, surfaces and text, accent. The accent is for the main action and the few things that must be noticed; used everywhere, it stops meaning anything.
- Text is never pure grey on a colored background: tint it toward the background's hue.
- Borders are a tint of the text color at low strength, not a separate grey.
- One elevation style: either borders or shadows, not both on the same element. Shadows are soft, low and few.

## Layout
- A container with a max width (about 1100 to 1200 px for a page, 640 to 720 for reading), centered, with side padding of at least 16 px on a phone and 32 on desktop.
- Align to a few shared edges. Every element's left edge should line up with something else.
- Break the sameness: not every section is a row of three equal cards. Vary width, give one item more room, let one picture run large.
- On a phone, one column, the main action within thumb reach, tap targets at least 44 px.

## Finish
- Every interactive element has four states styled: rest, hover, focus (visible), disabled.
- Corners follow one radius from `DESIGN.md`; an inner corner is smaller than the outer one it sits in.
- Icons match the text beside them in size and weight, and sit on its baseline.
- No default browser styling left next to styled controls.

## Check yourself
Squint at the screenshot: can you still tell what leads and where the groups are? If not, fix hierarchy and spacing before touching anything else.
