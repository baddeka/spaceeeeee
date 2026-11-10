---
name: match-reference
description: Use when the user gives a look to follow: an attached screenshot or mockup, a Figma link, or the name or address of a site. How to take the design from it and check your page against it.
---

# Build from a reference

A reference is the brief. The user picked it because they want that, not your own idea of good.

## 1. Read it before you write anything
Open every attached image with Read; read a Figma link with the Figma tools; for a site, look at it with `sh .rens-office/shot <address> --out .rens-office/shots/reference`. Then write down, in your plan:
- **Colors:** background, surface, text, muted text, accent, as hex values taken from the picture.
- **Type:** serif, sans or mono; the weight of headings; how much bigger a heading is than body text; letter spacing and case of labels. Name the closest Google Fonts family.
- **Layout:** the grid (columns, max width), what is centered and what is left-aligned, how much empty space surrounds the content.
- **Shapes:** corner radius, border thickness, shadows or none, how dense the controls are.
- **The signature:** the one or two things that make it look like itself: an oversized number, a tilted card, a thick outline, a photo that bleeds off the edge. Lose these and the page is a different design.

## 2. Build with those values
Put them in CSS variables first, then build. Reproduce the structure of the reference for the parts it shows; for parts it does not show, extend the same rules rather than inventing new ones. Use the user's own content, never the text in the reference.

## 3. Compare side by side
After building, take your screenshots and open yours and the reference one after the other. Check in this order: overall light and dark balance, proportions and whitespace, type size and weight, colors, the signature details. List every difference you see, fix the biggest three, and look again. Stop when what is left is content, not style.

## Limits
- Do not copy logos, brand names, photos or illustrations from a reference; take the style, and use the user's assets or neutral stand-ins.
- If the reference contradicts `DESIGN.md`, the newer instruction from the user wins; say which one you followed.
- If a picture is too small to read exact values, say what you assumed.
