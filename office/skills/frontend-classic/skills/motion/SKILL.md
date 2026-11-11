---
name: motion
description: Use when adding animation or transitions, or when a page feels lifeless. Where movement helps, how long it lasts, and how to keep it from looking generated.
---

# Movement

Movement should explain something: what changed, where it came from, what can be pressed. Decoration that moves is noise.

## Spend it in one place
Choose the one moment that matters for this product (the ticket being drawn, the timer ending, the order confirmed) and give it a small, well-timed sequence. Everything else stays quiet. Fading every section in on scroll and lifting every card on hover is the default that marks a page as generated.

## What deserves movement
- **An answer to an action:** a pressed button, an opened panel, an item added or removed. The visitor should see where it went.
- **A change of state:** loading to loaded, saved, error.
- **The one signature moment** above.

## Timing
- 120 to 200 ms for small things (hover, press, a toggle); 200 to 350 ms for panels and dialogs; up to about 600 ms for the signature moment.
- Things entering ease out (fast then slow); things leaving ease in. Never `linear` except for a spinner.
- Leaving is faster than entering.

## How
- Animate only `transform` and `opacity`. Animating size, position or shadow makes the page stutter.
- CSS transitions and keyframes first. Reach for a library only for a sequence CSS cannot express.
- Movement starts from where the thing came from: a menu grows from its button, a toast slides from the edge it lives on.
- Distances are small: 4 to 12 px for interface elements.

## Always
- Respect `prefers-reduced-motion`: replace movement with an instant change or a short fade.
- Nothing loops forever except a loading indicator, and nothing moves while the visitor reads.
- Content is never hidden waiting for an animation: if the script fails, the page must still show everything.
- Focus outlines appear at once, without a transition.

After adding movement, look at the page with the shot tool: the screenshot must show the finished state, not an element caught half-faded.
