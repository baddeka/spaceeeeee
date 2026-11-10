"""A project's page served for looking at: read-only, and on its own port, so it can't reach the office."""

from __future__ import annotations

import mimetypes
import re
import threading
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

# Folders a build writes its pages to, and folders a project keeps its front end in.
BUILT = ("dist", "build", "out", "_site")
FRONTS = ("", "frontend", "client", "web", "app", "site")
PLAIN = (*FRONTS, "public", "docs", "static", "src")
# A page whose scripts need a bundler (Vite and the like) shows nothing when opened as it is.
NEEDS_BUNDLER = re.compile(r"""<script[^>]+src=["']/?src/[^"']+\.(?:jsx?|tsx?|mjs|vue|svelte)["']""", re.IGNORECASE)
TYPES = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".svg": "image/svg+xml",
    ".json": "application/json",
    ".webmanifest": "application/manifest+json",
    ".wasm": "application/wasm",
    ".woff2": "font/woff2",
}


def find_page(workspace: Path) -> tuple[Path, str] | None:
    """The folder to serve and the page in it that shows the project, or None when no page opens as it is.

    A built page wins over its source: `dist/index.html` is what the visitor gets.
    """
    for front in FRONTS:
        for built in BUILT:
            folder = workspace / front / built
            if (folder / "index.html").is_file():
                return folder, "index.html"
    for front in PLAIN:
        folder = workspace / front
        if _opens_as_is(folder / "index.html"):
            return folder, "index.html"
    try:
        pages = [p for p in workspace.glob("*.html") if _opens_as_is(p)]
    except OSError:
        return None
    if pages:
        return workspace, max(pages, key=lambda p: p.stat().st_mtime).name
    return None


def _opens_as_is(page: Path) -> bool:
    try:
        return page.is_file() and not NEEDS_BUNDLER.search(page.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return False


def make_handler(root: Callable[[], Path | None], hosts: set[str] | None = None):
    """A handler that serves the files under `root()`, which may change between requests."""

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):  # keep the terminal quiet
            pass

        def do_GET(self):
            self._serve(body=True)

        def do_HEAD(self):
            self._serve(body=False)

        def _serve(self, body: bool) -> None:
            if hosts is not None:
                try:
                    host = urlsplit(f"//{self.headers.get('Host', '')}").hostname or ""
                except ValueError:
                    host = ""
                if host not in hosts:
                    return self._answer(HTTPStatus.FORBIDDEN, b"forbidden host", "text/plain", body)
            file = self._file()
            if file is None:
                return self._answer(HTTPStatus.NOT_FOUND, b"not found", "text/plain", body)
            try:
                data = file.read_bytes()
            except OSError:
                return self._answer(HTTPStatus.NOT_FOUND, b"not found", "text/plain", body)
            kind = TYPES.get(file.suffix.lower()) or mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            self._answer(HTTPStatus.OK, data, kind, body)

        def _file(self) -> Path | None:
            folder = root()
            if folder is None:
                return None
            parts = [part for part in unquote(urlsplit(self.path).path).split("/") if part]
            # Nothing hidden (.git, .env, the office's own folder), and nothing outside the folder.
            if any(part.startswith(".") or "\\" in part or "\x00" in part for part in parts):
                return None
            folder = folder.resolve()
            target = folder.joinpath(*parts).resolve()
            if not target.is_relative_to(folder):
                return None
            if target.is_dir():
                target = target / "index.html"
            if target.is_file():
                return target
            # An address without a file behind it is a route the page handles itself.
            if "." not in (parts[-1] if parts else "") and (folder / "index.html").is_file():
                return folder / "index.html"
            return None

        def _answer(self, status: int, data: bytes, kind: str, body: bool) -> None:
            self.send_response(status)
            text = kind.startswith("text/") or kind in ("application/json", "image/svg+xml", "application/manifest+json")
            self.send_header("Content-Type", f"{kind}; charset=utf-8" if text else kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if body:
                self.wfile.write(data)

    return Handler


def serve(
    root: Callable[[], Path | None],
    host: str = "127.0.0.1",
    port: int = 0,
    hosts: set[str] | None = None,
    server_class: type[ThreadingHTTPServer] = ThreadingHTTPServer,
) -> ThreadingHTTPServer:
    """Starts serving `root()` in the background; the caller shuts the server down."""
    server = server_class((host, port), make_handler(root, hosts))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
