---
name: frontend-verify
description: Use after building or changing a UI, before saying it is done. How to look at your own page in a real browser with the office's shot tool, and fix what you see.
---

# Look at what you built

Reading the code is not enough for a UI: open it and look. The office has a tool for that, and runs the same look before every review, so a page that fails it comes straight back to you.

## 1. Build first
If the project has a build or a type check (`npm run build`, `npx tsc --noEmit`, a linter), run it and fix every error. A project with a build step is shown from its built page (`dist/`, `build/`), so build it before you finish.

## 2. One command, one look
```sh
sh .rens-office/shot index.html
```
The target is a file, a folder, or an address such as `http://localhost:5173` when the app needs its own server (start it in the background first, stop it when you are done). On Windows without a POSIX shell, run `.rens-office\shot.cmd` instead.

It saves `desktop.png` (1280x800) and `phone.png` (390x844) into `.rens-office/shots/` and prints what is wrong:
- **script error**: an exception or `console.error`. Fix it.
- **failed to load**: one of the page's own files is missing. Fix the path or add the file.
- **the page is N px wider than the screen**: the phone layout overflows; it names the elements that stick out.
- **hard to read (check by eye)**: text whose contrast looks too low. Look at it in the picture; fix it if it really is.

Then open both pictures with Read and look at them like a visitor would.

## 3. Screens behind a click
Put the whole flow in the same command, so one call shows every state:
```sh
sh .rens-office/shot index.html fill=#name::Ada click=#add shot=added click=#open-settings shot=settings
```
Steps: `click=SELECTOR`, `fill=SELECTOR::TEXT`, `press=Enter`, `hover=SELECTOR`, `scroll=SELECTOR`, `goto=#/route`, `wait=500`, `shot=NAME`, `eval=JAVASCRIPT`. Add `--full` to photograph a long page a screen at a time, `--only phone` to look at one size. `sh .rens-office/shot --help` lists everything.

Show the states that matter: the empty one, the filled one, an error, and the main action done.

## 4. Judge the pictures
For each picture, check, in this order:
1. Is it the style in `DESIGN.md`: its colors, its two fonts, its shapes?
2. Does one thing lead on the screen, and is the main action obvious?
3. Are gaps between like things equal, and do edges line up?
4. Can every text be read: size, contrast, line length, nothing cut off or overlapping?
5. On the phone: nothing cut off at the right, controls big enough to tap, a layout made for a phone rather than a squeezed desktop.
6. Any leftovers: placeholder text, a missing image, an unstyled button or input?

Fix what you find, then run the same command again. Two or three rounds are normal; stop when a round finds nothing.

## 5. Keep it cheap
- One command per look. Do not write a new script for each check.
- Look again only after you changed something.
- If the tool says no browser was found, use Playwright when the project already has it; otherwise check with `curl` that the page answers and say plainly that nobody looked at it.

In your final message, say which screens you looked at, at which sizes, and what you fixed after looking.
