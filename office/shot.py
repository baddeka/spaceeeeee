"""`shot`: a look at a page from the command line, for the agents and for people.

    python -m office.shot index.html
    python -m office.shot http://localhost:5173 --full
    python -m office.shot index.html fill=#name::Ada click=#add shot=added
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):  # run as a file, the way the office's launcher in a project does
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "office"

from .eyes import DEVICES, NO_BROWSER, STEPS, LookError, find_browser, look  # noqa: E402

SHOTS_DIR = Path(".rens-office") / "shots"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="shot",
        description="Opens a page in the browser on this computer at a desktop and a phone size, saves "
        "screenshots, and lists script errors, files that failed to load and a layout wider than the phone.",
        epilog=STEPS,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("target", help="an address, or a file or folder on this computer")
    parser.add_argument("steps", nargs="*", help="what to do on the page before the screenshot (see below)")
    parser.add_argument("--out", help=f"folder for the screenshots (default: {SHOTS_DIR.as_posix()})")
    parser.add_argument("--full", action="store_true", help="also photograph the rest of a long page, a screen at a time")
    parser.add_argument("--only", choices=sorted(DEVICES), help="look on one device only")
    args = parser.parse_args(argv)

    if find_browser() is None:
        print(NO_BROWSER, file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else SHOTS_DIR
    devices = (DEVICES[args.only],) if args.only else tuple(DEVICES.values())
    try:
        seen = look(args.target, out, steps=args.steps, full=args.full, devices=devices)
    except LookError as e:
        print(f"shot: {e}", file=sys.stderr)
        return 1
    print(seen.report(Path.cwd()))
    print("Open the pictures with the Read tool to see the page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
