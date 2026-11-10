---
name: design-review
description: Use when the office gives you screenshots of the page. How to review what the page looks like, not only its code, and how to report it so the developer can fix it.
---

# Review how the page looks

Open every screenshot the office named with the Read tool: the desktop one first, then the phone one. Judge the picture, then find the cause in the code.

## What to look for
1. **The chosen style.** If the project has `DESIGN.md`, read it. The page must use its colors, its two fonts and its shapes. A page that ignores them is a major issue, however tidy it is.
2. **Hierarchy.** One thing should lead on each screen: the headline or the main action. Report a screen where everything has the same weight, or where the main action is hard to find.
3. **Spacing and alignment.** Uneven gaps between like things, edges that almost line up, text touching a border, content cramped at one side with empty space at the other.
4. **Text.** Lines too long to read (over about 80 characters), text too small on the phone (under 14px), text that is cut off, overlaps something or wraps one orphan word. Low contrast between text and what is behind it.
5. **The phone.** Anything cut off at the right edge, controls too small to tap (under about 44px), a layout that is only the desktop one squeezed.
6. **Leftovers.** Placeholder text (lorem ipsum, "Title here"), broken or missing images, default browser styling on buttons and inputs next to styled ones, an empty state that says nothing.
7. **Sameness.** A page that could belong to any product: the same rounded cards, one accent and a gradient, with nothing of the product's own. Report it as minor with one concrete suggestion, unless `DESIGN.md` asked for exactly that.

## How to report
- Each issue names the screen (desktop or phone), the element, and what is wrong in a few words: "phone: the Add button is cut off at the right edge".
- Point `file` and `line` at the rule or markup that causes it when you can find it; otherwise at the stylesheet.
- Severity: **major** when something cannot be read or used, is broken on the phone, or the chosen style is ignored; **minor** for uneven spacing, weak hierarchy and leftovers; **nit** for polish.
- The suggestion says what to change, with the value when you can: "set `max-width: 68ch` on `.lead`".
- Do not report taste. "I would have used blue" is not an issue; "the accent in DESIGN.md is #2346B8 and the buttons are grey" is.

The screenshots show one state of the page. For states you cannot see (errors, empty lists, open dialogs), review the code as usual.
