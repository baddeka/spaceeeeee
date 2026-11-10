"""Eyes for the office: a page seen through the browser already on this computer.

Chrome, Edge and their relatives all speak the DevTools protocol, so nothing has to be installed.
This finds one of them, opens a page at a desktop and a phone size, takes screenshots, and reports
what a person would notice first: script errors, files that failed to load, a page wider than the
phone, and text too faint to read.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from reviewer.processes import kill_tree

from .preview import serve

BROWSER_ENV = "RENS_OFFICE_BROWSER"
ON_PATH = (
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
    "microsoft-edge",
    "microsoft-edge-stable",
    "brave-browser",
    "chrome",
    "msedge",
)
ON_WINDOWS = (
    "Google/Chrome/Application/chrome.exe",
    "Microsoft/Edge/Application/msedge.exe",
    "BraveSoftware/Brave-Browser/Application/brave.exe",
    "Chromium/Application/chrome.exe",
)
ON_MAC = (
    "Google Chrome.app/Contents/MacOS/Google Chrome",
    "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "Chromium.app/Contents/MacOS/Chromium",
    "Brave Browser.app/Contents/MacOS/Brave Browser",
)
FROM_PLAYWRIGHT = (
    "chromium-*/chrome-linux*/chrome",
    "chromium-*/chrome-win*/chrome.exe",
    "chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
    "chromium-*/chrome-mac*/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
)
NO_BROWSER = (
    f"No Chrome, Edge or Chromium was found on this computer. Install one, or set {BROWSER_ENV} to the path of one."
)

START_SECONDS = 20
LOAD_SECONDS = 20
CALL_SECONDS = 20
QUIET_SECONDS = 0.4  # nothing loading for this long: the page has settled
SETTLE_SECONDS = 1.0  # after that, the time entrance animations get to finish
SETTLE_LIMIT = 6.0
MAX_TILES = 4
MAX_WAIT_MS = 10_000
MAX_LISTED = 8  # problems of one kind listed in a report


class LookError(Exception):
    """The page could not be looked at: no browser, it did not start, or the page did not open."""


@dataclass(frozen=True)
class Device:
    name: str
    width: int
    height: int
    scale: float
    mobile: bool


DESKTOP = Device("desktop", 1280, 800, 1, False)
PHONE = Device("phone", 390, 844, 2, True)
DEVICES = {device.name: device for device in (DESKTOP, PHONE)}
PHONE_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)


@dataclass
class View:
    """What one device showed."""

    device: Device
    shots: list[Path] = field(default_factory=list)
    overflow: int = 0  # how many pixels wider than the screen the page is
    wide: list[str] = field(default_factory=list)  # the elements that stick out
    faint: list[str] = field(default_factory=list)  # text with too little contrast, as far as it can be told
    blank: bool = False


@dataclass
class Look:
    url: str
    views: list[View] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)  # script errors
    failed: list[str] = field(default_factory=list)  # the page's own files that did not load
    offline: list[str] = field(default_factory=list)  # other sites' files that did not load (fonts, CDNs)
    notes: list[str] = field(default_factory=list)  # what `eval` steps returned, and dialogs the page opened

    def problems(self) -> list[str]:
        """What is broken, whoever looks: errors, missing files, a page wider than the phone, nothing on it."""
        found = [f"script error: {error}" for error in self.errors[:MAX_LISTED]]
        found += [f"failed to load: {request}" for request in self.failed[:MAX_LISTED]]
        for view in self.views:
            if view.blank:
                found.append(f"{view.device.name}: the page shows nothing")
            if view.overflow and view.device.mobile:
                sticking = f": {'; '.join(view.wide)}" if view.wide else ""
                found.append(f"{view.device.name}: the page is {view.overflow}px wider than the screen{sticking}")
        return found

    def report(self, base: Path | None = None) -> str:
        """The look in words, for whoever asked for it; paths are shown relative to `base`."""

        def shown(path: Path) -> str:
            try:
                return path.relative_to(base).as_posix() if base else str(path)
            except ValueError:
                return str(path)

        lines = []
        for view in self.views:
            device = view.device
            lines.append(f"{device.name} {device.width}x{device.height}")
            lines += [f"  {shown(shot)}" for shot in view.shots]
        problems = self.problems()
        lines += ["problems", *(f"  {problem}" for problem in problems)] if problems else ["no problems found"]
        faint = [f"{view.device.name}: {text}" for view in self.views for text in view.faint]
        if faint:
            lines += ["hard to read (check by eye)", *(f"  {text}" for text in faint[:MAX_LISTED])]
        desktop = [view for view in self.views if view.overflow and not view.device.mobile]
        if desktop:
            lines.append(f"note: at {desktop[0].device.width}px the page scrolls sideways by {desktop[0].overflow}px")
        if self.offline:
            lines += ["not loaded from other sites", *(f"  {request}" for request in self.offline[:MAX_LISTED])]
        lines += [f"note: {note}" for note in self.notes]
        return "\n".join(lines)


def find_browser() -> str | None:
    """The path of a browser that can be driven, or None."""
    chosen = os.environ.get(BROWSER_ENV)
    if chosen:
        return chosen if Path(chosen).is_file() else shutil.which(chosen)
    for name in ON_PATH:
        if found := shutil.which(name):
            return found
    candidates: list[Path] = []
    if sys.platform == "win32":
        for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            if base := os.environ.get(variable):
                candidates += [Path(base) / relative for relative in ON_WINDOWS]
    elif sys.platform == "darwin":
        for base in (Path("/Applications"), Path.home() / "Applications"):
            candidates += [base / relative for relative in ON_MAC]
    candidates += _playwright_browsers()
    return next((str(path) for path in candidates if path.is_file()), None)


def _playwright_browsers() -> list[Path]:
    """Chromium builds Playwright downloaded, newest first."""
    if root := os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        roots = [Path(root)]
    else:
        home = Path.home()
        roots = [home / ".cache/ms-playwright", home / "Library/Caches/ms-playwright"]
        if local := os.environ.get("LOCALAPPDATA"):
            roots.append(Path(local) / "ms-playwright")
    found: list[Path] = []
    for base in roots:
        if base.is_dir():
            for pattern in FROM_PLAYWRIGHT:
                found += sorted(base.glob(pattern), reverse=True)
    return found


def look(
    target: str,
    out: Path,
    *,
    steps: tuple[str, ...] | list[str] = (),
    full: bool = False,
    devices: tuple[Device, ...] = (DESKTOP, PHONE),
    browser: str | None = None,
    on_browser: Callable[[subprocess.Popen], None] | None = None,
) -> Look:
    """Opens `target` on each device and returns what was seen; screenshots go into `out`.

    `target` is an address, or a file or folder on this computer, which is served for the look.
    `steps` act on the page like a visitor (see STEPS). `on_browser` receives the browser's process
    as soon as it exists, so the caller can end it early.
    """
    path = browser or find_browser()
    if path is None:
        raise LookError(NO_BROWSER)
    server = None
    if urlsplit(target).scheme in ("http", "https"):
        url = target
    else:
        local = Path(target).expanduser().resolve()
        if not local.exists():
            raise LookError(f"there is no such file or folder: {target}")
        folder = local if local.is_dir() else local.parent
        server = serve(lambda: folder)
        url = f"http://127.0.0.1:{server.server_port}/" + ("" if local.is_dir() else local.name)
    out.mkdir(parents=True, exist_ok=True)
    result = Look(url=url)
    chrome = None
    try:
        chrome = _Chrome(path, on_browser)
        for device in devices:
            result.views.append(_Visit(chrome, device, out, result).run(url, list(steps), full))
    finally:
        if chrome is not None:
            chrome.close()
        if server is not None:
            server.shutdown()
            server.server_close()
    for name in ("errors", "failed", "offline", "notes"):
        setattr(result, name, list(dict.fromkeys(getattr(result, name))))  # the two devices see the same ones
    return result


STEPS = """\
Steps act on the page like a visitor, in order, on each device:
  click=SELECTOR          click the first element that matches
  fill=SELECTOR::TEXT     type TEXT into a field
  press=KEY               press Enter, Escape, Tab, Space, ArrowDown ... or one character
  hover=SELECTOR          move the pointer over an element
  scroll=SELECTOR|PIXELS  scroll an element into view, or the page to a position
  goto=ADDRESS            open another page, or a #route of this one
  wait=MILLISECONDS       wait, for something that takes time
  shot=NAME               save a screenshot now, as NAME-desktop.png and NAME-phone.png
  eval=JAVASCRIPT         report what an expression returns
With steps, a screenshot is saved at each shot= and at the end."""


class _Socket:
    """Just enough of a WebSocket client for the DevTools protocol: text messages to a local browser."""

    def __init__(self, port: int, path: str):
        self._sock = socket.create_connection(("127.0.0.1", port), timeout=CALL_SECONDS)
        self._buffer = bytearray()
        self._parts: list[bytes] = []  # a message that arrives in several frames
        key = base64.b64encode(os.urandom(16)).decode()
        self._sock.sendall(
            (
                f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
            ).encode()
        )
        deadline = time.monotonic() + CALL_SECONDS
        while b"\r\n\r\n" not in self._buffer:
            if not self._fill(deadline):
                raise LookError("the browser did not answer")
        head, _, rest = bytes(self._buffer).partition(b"\r\n\r\n")
        if b" 101 " not in head.split(b"\r\n", 1)[0] + b" ":
            raise LookError("the browser refused the connection")
        self._buffer = bytearray(rest)

    def send(self, text: str) -> None:
        self._frame_out(0x1, text.encode())

    def receive(self, deadline: float) -> str | None:
        """The next message, or None when none came by `deadline`."""
        while True:
            frame = self._frame_in()
            if frame is None:
                if not self._fill(deadline):
                    return None
                continue
            final, opcode, payload = frame
            if opcode == 0x8:
                raise LookError("the browser closed the connection")
            if opcode == 0x9:
                self._frame_out(0xA, payload)
            elif opcode in (0x0, 0x1, 0x2):
                self._parts.append(payload)
                if final:
                    message = b"".join(self._parts)
                    self._parts.clear()
                    return message.decode("utf-8", errors="replace")

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass

    def _fill(self, deadline: float) -> bool:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        self._sock.settimeout(remaining)
        try:
            chunk = self._sock.recv(1 << 16)
        except TimeoutError:
            return False
        except OSError as e:
            raise LookError(f"lost the browser: {e}") from None
        if not chunk:
            raise LookError("the browser closed the connection")
        self._buffer += chunk
        return True

    def _frame_in(self) -> tuple[bool, int, bytes] | None:
        """Takes one whole frame out of the buffer, or None while it is still arriving."""
        buffer = self._buffer
        if len(buffer) < 2:
            return None
        length = buffer[1] & 0x7F
        start = 2
        if length == 126:
            if len(buffer) < 4:
                return None
            length, start = struct.unpack(">H", buffer[2:4])[0], 4
        elif length == 127:
            if len(buffer) < 10:
                return None
            length, start = struct.unpack(">Q", buffer[2:10])[0], 10
        if buffer[1] & 0x80:
            raise LookError("the browser sent a frame it should not")  # servers never mask
        if len(buffer) < start + length:
            return None
        frame = bool(buffer[0] & 0x80), buffer[0] & 0x0F, bytes(buffer[start : start + length])
        del buffer[: start + length]
        return frame

    def _frame_out(self, opcode: int, data: bytes) -> None:
        head = bytearray([0x80 | opcode])
        if len(data) < 126:
            head.append(0x80 | len(data))
        elif len(data) < 1 << 16:
            head.append(0x80 | 126)
            head += struct.pack(">H", len(data))
        else:
            head.append(0x80 | 127)
            head += struct.pack(">Q", len(data))
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[n % 4] for n, byte in enumerate(data))  # a client must mask what it sends
        self._sock.settimeout(CALL_SECONDS)
        try:
            self._sock.sendall(bytes(head) + mask + masked)
        except OSError as e:
            raise LookError(f"lost the browser: {e}") from None


class _Chrome:
    """A headless browser with a profile of its own, and the connection that drives it."""

    def __init__(self, path: str, on_browser: Callable[[subprocess.Popen], None] | None = None):
        self._profile = tempfile.mkdtemp(prefix="rens-office-browser-")
        self._proc: subprocess.Popen | None = None
        self._socket: _Socket | None = None
        self._id = 0
        self.on_event: Callable[[dict], None] = lambda message: None
        args = [
            path,
            "--headless=new",
            f"--user-data-dir={self._profile}",
            "--remote-debugging-port=0",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-gpu",
            "--hide-scrollbars",
            "--mute-audio",
            "about:blank",
        ]
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            args.insert(1, "--no-sandbox")  # the browser refuses to start as root with its sandbox on
        try:
            self._proc = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            if on_browser:
                on_browser(self._proc)
            port, address = self._where()
            self._socket = _Socket(port, address)
        except OSError as e:
            self.close()
            raise LookError(f"could not start the browser {path}: {e}") from None
        except BaseException:
            self.close()
            raise

    def _where(self) -> tuple[int, str]:
        """The port and address the browser listens on, which it writes into its profile once it is up."""
        file = Path(self._profile) / "DevToolsActivePort"
        deadline = time.monotonic() + START_SECONDS
        while time.monotonic() < deadline:
            try:
                lines = file.read_text(encoding="utf-8").split()
            except OSError:
                lines = []
            if len(lines) >= 2 and lines[0].isdigit():
                return int(lines[0]), lines[1]
            if self._proc is not None and self._proc.poll() is not None:
                raise LookError("the browser exited as soon as it started")
            time.sleep(0.05)
        raise LookError("the browser did not start in time")

    def call(self, method: str, params: dict | None = None, session: str | None = None, timeout: float = CALL_SECONDS):
        """Sends one command and returns its result; what arrives meanwhile goes to `on_event`."""
        assert self._socket is not None
        self._id += 1
        message = {"id": self._id, "method": method, "params": params or {}}
        if session:
            message["sessionId"] = session
        self._socket.send(json.dumps(message))
        deadline = time.monotonic() + timeout
        while True:
            answer = self._next(deadline)
            if answer is None:
                raise LookError(f"the browser did not answer {method} in time")
            if answer.get("id") == self._id:
                if "error" in answer:
                    raise LookError(f"{method}: {answer['error'].get('message', 'failed')}")
                return answer.get("result", {})
            self.on_event(answer)

    def tell(self, method: str, params: dict, session: str) -> None:
        """Sends a command without waiting for its answer."""
        assert self._socket is not None
        self._id += 1
        self._socket.send(json.dumps({"id": self._id, "method": method, "params": params, "sessionId": session}))

    def pump(self, seconds: float) -> None:
        """Takes in what the browser reports for `seconds`."""
        deadline = time.monotonic() + seconds
        while (message := self._next(deadline)) is not None:
            self.on_event(message)

    def _next(self, deadline: float) -> dict | None:
        assert self._socket is not None
        text = self._socket.receive(deadline)
        if text is None:
            return None
        try:
            message = json.loads(text)
        except ValueError:
            return {}
        return message if isinstance(message, dict) else {}

    def close(self) -> None:
        if self._socket is not None:
            self._socket.close()
        if self._proc is not None:
            kill_tree(self._proc, force=True)
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        for _ in range(5):  # Windows lets go of the profile's files a moment after the browser ends
            shutil.rmtree(self._profile, ignore_errors=True)
            if not os.path.exists(self._profile):
                break
            time.sleep(0.2)


KEYS = {
    "Enter": (13, "\r"),
    "Tab": (9, ""),
    "Escape": (27, ""),
    "Backspace": (8, ""),
    "Delete": (46, ""),
    "Space": (32, " "),
    "ArrowLeft": (37, ""),
    "ArrowUp": (38, ""),
    "ArrowRight": (39, ""),
    "ArrowDown": (40, ""),
    "PageUp": (33, ""),
    "PageDown": (34, ""),
    "End": (35, ""),
    "Home": (36, ""),
}

# Where to click: the middle of the element, once it is in view.
POINT_JS = """(selector) => {
  const el = document.querySelector(selector);
  if (!el) return null;
  el.scrollIntoView({ block: 'center', inline: 'center' });
  const r = el.getBoundingClientRect();
  return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
}"""

# Typing the way a framework notices: through the field's own setter, then the events a keyboard sends.
FILL_JS = """(selector, text) => {
  const el = document.querySelector(selector);
  if (!el) return null;
  el.focus();
  if (el.isContentEditable) {
    el.textContent = text;
  } else {
    const kind = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement
      : el instanceof HTMLSelectElement ? HTMLSelectElement : HTMLInputElement;
    Object.getOwnPropertyDescriptor(kind.prototype, 'value').set.call(el, text);
  }
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
  return true;
}"""

SCROLL_JS = """(where) => {
  if (/^\\d+$/.test(where)) { window.scrollTo(0, Number(where)); return true; }
  const el = document.querySelector(where);
  if (!el) return null;
  el.scrollIntoView({ block: 'start' });
  return true;
}"""

# What a look reports besides the picture: is the page wider than the screen (and what sticks out),
# is anything on it, and which text in view has too little contrast against a plain background.
FACTS_JS = """(() => {
  const doc = document.documentElement;
  const body = document.body;
  if (!body) return { overflow: 0, wide: [], faint: [], blank: true, height: 0 };
  // The layout's width: a phone zooms out to fit a page that is too wide, which widens innerWidth.
  const width = doc.clientWidth || window.innerWidth;
  const overflow = Math.max(0, Math.max(doc.scrollWidth, body.scrollWidth) - width);
  const name = (el) => {
    let text = el.tagName.toLowerCase();
    if (el.id) text += '#' + el.id;
    else if (el.classList.length) text += '.' + [...el.classList].slice(0, 2).join('.');
    return text;
  };
  const wide = [];
  if (overflow > 1) {
    const clipped = (el) => {
      for (let up = el.parentElement; up && up !== body; up = up.parentElement) {
        const flow = getComputedStyle(up).overflowX;
        if (flow !== 'visible' && up.getBoundingClientRect().right <= width + 1) return true;
      }
      return false;
    };
    for (const el of body.querySelectorAll('*')) {
      if (wide.length >= 3) break;
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.right > width + 1 && !wide.some((w) => w.el.contains(el)) && !clipped(el)) {
        wide.push({ el, text: `${name(el)} (${Math.round(r.right - width)}px past the edge)` });
      }
    }
  }
  const parse = (color) => {
    const found = /^rgba?\\(([^)]+)\\)$/.exec(color);
    if (!found) return null;
    const parts = found[1].split(/[\\s,\\/]+/).filter(Boolean).map(Number);
    return parts.length < 3 || parts.some(Number.isNaN) ? null
      : { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 };
  };
  const light = ({ r, g, b }) => {
    const part = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * part(r) + 0.7152 * part(g) + 0.0722 * part(b);
  };
  const contrast = (one, two) => {
    const [high, low] = [light(one), light(two)].sort((p, q) => q - p);
    return (high + 0.05) / (low + 0.05);
  };
  // The plain colour behind an element, or null when a picture, a gradient or a see-through layer is there.
  const behind = (el, x, y) => {
    const stack = document.elementsFromPoint(x, y);
    const from = stack.indexOf(el);
    if (from < 0) return null;
    for (const layer of stack.slice(from)) {
      if (layer !== el && /^(img|video|canvas|svg|picture|iframe)$/i.test(layer.tagName)) return null;
      const style = getComputedStyle(layer);
      if (style.backgroundImage !== 'none' || Number(style.opacity) < 0.99) return null;
      const color = parse(style.backgroundColor);
      if (!color) return null;
      if (color.a >= 0.99) return color;
      if (color.a > 0.01) return null;
    }
    return { r: 255, g: 255, b: 255, a: 1 };
  };
  const faint = [];
  const seen = new Set();
  const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
  let checked = 0;
  while (walker.nextNode() && checked < 500 && faint.length < 6) {
    const words = walker.currentNode.textContent.trim();
    const el = walker.currentNode.parentElement;
    if (words.length < 2 || !el || seen.has(el)) continue;
    seen.add(el);
    if (el.closest('[disabled], [aria-disabled="true"], [aria-hidden="true"]')) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1 || r.bottom < 0 || r.top > window.innerHeight) continue;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden') continue;
    checked += 1;
    const ink = parse(style.color);
    const paper = behind(el, Math.min(width - 1, Math.max(0, r.left + Math.min(r.width / 2, 12))), r.top + r.height / 2);
    if (!ink || ink.a < 0.99 || !paper) continue;
    const size = parseFloat(style.fontSize);
    const needs = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700) ? 3 : 4.5;
    const has = contrast(ink, paper);
    if (has < needs - 0.05) {
      faint.push(`${name(el)} "${words.slice(0, 32)}" has ${has.toFixed(1)}:1, needs ${needs}:1`);
    }
  }
  const blank = !(body.innerText || '').trim() && !body.querySelector('img, svg, canvas, video, iframe');
  return { overflow, wide: wide.map((w) => w.text), faint, blank, height: Math.max(doc.scrollHeight, body.scrollHeight) };
})()"""


class _Visit:
    """One device's visit to the page: open it, act on it, photograph it, note what went wrong."""

    def __init__(self, chrome: _Chrome, device: Device, out: Path, result: Look):
        self.chrome = chrome
        self.device = device
        self.out = out
        self.result = result
        self.view = View(device)
        self.session = ""
        self.origin = ""
        self.loaded = False
        self.loading: dict[str, str] = {}
        self._height = 0

    def run(self, url: str, steps: list[str], full: bool) -> View:
        chrome = self.chrome
        context = chrome.call("Target.createBrowserContext")["browserContextId"]  # nothing kept from a visit before
        try:
            target = chrome.call("Target.createTarget", {"url": "about:blank", "browserContextId": context})["targetId"]
            self.session = chrome.call("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
            chrome.on_event = self._on_event
            for domain in ("Page", "Runtime", "Log", "Network"):
                self._call(f"{domain}.enable")
            device = self.device
            self._call(
                "Emulation.setDeviceMetricsOverride",
                {"width": device.width, "height": device.height, "deviceScaleFactor": device.scale, "mobile": device.mobile},
            )
            if device.mobile:
                self._call("Emulation.setUserAgentOverride", {"userAgent": PHONE_AGENT})
                self._call("Emulation.setTouchEmulationEnabled", {"enabled": True})
            self._open(url)
            self._act(steps)
            if not steps or not steps[-1].startswith("shot="):
                self._shoot(f"{device.name}.png")
            self._facts()
            if full:
                self._tiles()
        finally:
            chrome.on_event = lambda message: None
            try:
                chrome.call("Target.disposeBrowserContext", {"browserContextId": context})
            except LookError:
                pass  # the browser is gone, and the look fails with what made it go
        return self.view

    # ----- the page -----

    def _call(self, method: str, params: dict | None = None, timeout: float = CALL_SECONDS) -> dict:
        return self.chrome.call(method, params, self.session, timeout)

    def _eval(self, expression: str, wait: bool = False):
        answer = self._call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": wait})
        if problem := answer.get("exceptionDetails"):
            raise LookError(_exception(problem))
        return answer.get("result", {}).get("value")

    def _apply(self, function: str, *args: str):
        return self._eval(f"({function})({', '.join(json.dumps(arg) for arg in args)})")

    def _open(self, url: str) -> None:
        self.origin = _origin(url)
        self.loaded = False
        answer = self._call("Page.navigate", {"url": url})
        if answer.get("errorText"):
            raise LookError(f"could not open {url}: {answer['errorText']}")
        deadline = time.monotonic() + LOAD_SECONDS
        while not self.loaded and time.monotonic() < deadline:
            self.chrome.pump(0.1)
        self._settle()
        try:
            self._eval("document.fonts ? document.fonts.ready.then(() => true) : true", wait=True)
        except LookError:
            pass  # fonts that never arrive are reported as files that failed to load
        self.chrome.pump(SETTLE_SECONDS)  # entrance animations finish

    def _settle(self, limit: float = SETTLE_LIMIT) -> None:
        """Waits until the page has stopped loading things, or `limit` seconds."""
        end = time.monotonic() + limit
        quiet_since = None
        while time.monotonic() < end:
            self.chrome.pump(0.1)
            if self.loading:
                quiet_since = None
            elif quiet_since is None:
                quiet_since = time.monotonic()
            elif time.monotonic() - quiet_since >= QUIET_SECONDS:
                return

    def _shoot(self, name: str) -> None:
        data = self._call("Page.captureScreenshot", {"format": "png"}, timeout=LOAD_SECONDS)["data"]
        file = self.out / name
        file.write_bytes(base64.b64decode(data))
        self.view.shots.append(file)

    def _facts(self) -> None:
        facts = self._eval(FACTS_JS) or {}
        view = self.view
        view.overflow = max(view.overflow, int(facts.get("overflow") or 0))
        view.wide = view.wide or list(facts.get("wide") or [])
        view.faint += [text for text in facts.get("faint") or [] if text not in view.faint]
        view.blank = bool(facts.get("blank"))
        self._height = int(facts.get("height") or 0)

    def _tiles(self) -> None:
        """The rest of a long page, a screen at a time, scrolled to as a visitor would."""
        device = self.device
        screens = min(MAX_TILES, -(-self._height // device.height))
        for n in range(1, screens):
            self._eval(f"window.scrollTo(0, {n * device.height})")
            self.chrome.pump(0.35)
            self._shoot(f"{device.name}-{n + 1}.png")
            self._facts()
        self._eval("window.scrollTo(0, 0)")

    # ----- steps -----

    def _act(self, steps: list[str]) -> None:
        for step in steps:
            name, _, value = step.partition("=")
            try:
                self._step(name.strip(), value)
            except LookError as e:
                raise LookError(f"step {step!r}: {e}") from None
            self.chrome.pump(0.3)
            self._settle(limit=3.0)

    def _step(self, name: str, value: str) -> None:
        if name == "click":
            self._point(value, click=True)
        elif name == "hover":
            self._point(value, click=False)
        elif name == "fill":
            selector, _, text = value.partition("::")
            self._found(self._apply(FILL_JS, selector, text), selector)
        elif name == "press":
            self._press(value)
        elif name == "scroll":
            self._found(self._apply(SCROLL_JS, value.strip()), value)
        elif name == "wait":
            if not value.strip().isdigit():
                raise LookError("give the time in milliseconds")
            self.chrome.pump(min(int(value), MAX_WAIT_MS) / 1000)
        elif name == "goto":
            if value.startswith("#"):
                self._eval(f"location.hash = {json.dumps(value)}")
            else:
                self._open(urljoin(self._eval("location.href") or self.result.url, value))
        elif name == "shot":
            safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in value.strip())[:40] or "shot"
            self._shoot(f"{safe}-{self.device.name}.png")
        elif name == "eval":
            returned = json.dumps(self._eval(value, wait=True), ensure_ascii=False)
            self.result.notes.append(f"{value[:60]} -> {(returned or 'undefined')[:300]}")
        else:
            raise LookError("unknown step; use click, fill, press, hover, scroll, goto, wait, shot or eval")

    def _found(self, answer, selector: str) -> None:
        if answer is None:
            raise LookError(f"no element matches {selector!r}")

    def _point(self, selector: str, click: bool) -> None:
        point = self._apply(POINT_JS, selector)
        self._found(point, selector)
        at = {"x": point["x"], "y": point["y"]}
        if click and self.device.mobile:
            # A phone has no mouse: a tap is a touch that starts and ends in one place.
            self._call("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [at]})
            self._call("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
            return
        self._call("Input.dispatchMouseEvent", {"type": "mouseMoved", **at})
        if click:
            pressed = {**at, "button": "left", "clickCount": 1}
            self._call("Input.dispatchMouseEvent", {"type": "mousePressed", **pressed})
            self._call("Input.dispatchMouseEvent", {"type": "mouseReleased", **pressed})

    def _press(self, key: str) -> None:
        key = key.strip() or " "
        if key in KEYS:
            code, text = KEYS[key]
            name = " " if key == "Space" else key
            down = {"type": "keyDown" if text else "rawKeyDown", "key": name, "code": key, "windowsVirtualKeyCode": code}
            if text:
                down["text"] = text
            up = {"type": "keyUp", "key": name, "code": key, "windowsVirtualKeyCode": code}
        elif len(key) == 1:
            down, up = {"type": "keyDown", "key": key, "text": key}, {"type": "keyUp", "key": key}
        else:
            raise LookError(f"unknown key; use one character or one of: {', '.join(KEYS)}")
        self._call("Input.dispatchKeyEvent", down)
        self._call("Input.dispatchKeyEvent", up)

    # ----- what the browser reports -----

    def _on_event(self, message: dict) -> None:
        if message.get("sessionId") != self.session:
            return
        method = message.get("method")
        params = message.get("params") or {}
        if method == "Page.loadEventFired":
            self.loaded = True
        elif method == "Page.javascriptDialogOpening":
            # A page that waits for an answer to alert() would never finish loading.
            self.chrome.tell("Page.handleJavaScriptDialog", {"accept": True}, self.session)
            kind = params.get("type", "dialog")
            self.result.notes.append(f"the page showed a dialog ({kind}): {str(params.get('message', ''))[:120]}")
        elif method == "Runtime.exceptionThrown":
            self.result.errors.append(_exception(params.get("exceptionDetails") or {}))
        elif method == "Runtime.consoleAPICalled" and params.get("type") in ("error", "assert"):
            words = [str(arg.get("value", arg.get("description", ""))) for arg in params.get("args") or []]
            self.result.errors.append(" ".join(words).strip()[:300] or "console.error")
        elif method == "Log.entryAdded":
            entry = params.get("entry") or {}
            if entry.get("level") == "error" and entry.get("source") != "network":  # the requests are noted below
                self.result.errors.append(str(entry.get("text", ""))[:300])
        elif method == "Network.requestWillBeSent":
            # A stream the page keeps open never finishes; it must not hold the look up.
            if params.get("type") not in ("EventSource", "WebSocket", "Media", "Ping"):
                self.loading[params.get("requestId", "")] = (params.get("request") or {}).get("url", "")
        elif method == "Network.responseReceived":
            response = params.get("response") or {}
            if int(response.get("status") or 0) >= 400:
                self._lost(str(response["status"]), response.get("url", ""))
        elif method == "Network.loadingFinished":
            self.loading.pop(params.get("requestId", ""), None)
        elif method == "Network.loadingFailed":
            url = self.loading.pop(params.get("requestId", ""), "")
            reason = params.get("errorText", "")
            if url and not params.get("canceled") and reason != "net::ERR_ABORTED":
                self._lost(reason, url)

    def _lost(self, why: str, url: str) -> None:
        if url.startswith("data:") or url.endswith("/favicon.ico"):
            return  # a page without an icon is not broken
        if _origin(url) == self.origin:
            # The page's own file: its path says which, and the port it was served on says nothing.
            parts = urlsplit(url)
            self.result.failed.append(f"{why} {parts.path}{'?' + parts.query if parts.query else ''}"[:300])
        else:
            self.result.offline.append(f"{why} {url}"[:300])


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _exception(details: dict) -> str:
    """A script error in one line: what it says and where."""
    text = (details.get("exception") or {}).get("description") or details.get("text") or "script error"
    first = str(text).strip().splitlines()[0] if str(text).strip() else "script error"
    where = Path(urlsplit(details.get("url") or "").path).name
    line = details.get("lineNumber")
    return f"{first[:240]} ({where}:{line + 1})" if where and isinstance(line, int) else first[:240]
