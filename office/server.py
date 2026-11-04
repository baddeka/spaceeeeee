"""Local web server for the office: `ai-office --workspace ./my-project`."""

from __future__ import annotations

import argparse
import json
import queue
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from reviewer.context import ContextError

from .agents import WORKER_TOOLS, Busy, Office
from .i18n import LANGUAGES

STATIC_DIR = Path(__file__).parent / "static"
STATIC_TYPES = {".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".woff2": "font/woff2"}
LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1"}
WILDCARD_HOSTS = {"", "0.0.0.0", "::"}
HEARTBEAT_SECONDS = 15
FORBIDDEN_HOST = "forbidden host: open the page by an allowed name, or start ai-office with --allow-host NAME"


def allowed_hosts(bind_host: str, extra: list[str] | None = None) -> set[str]:
    """Names the page may be opened by. Any other Host header is refused, which stops DNS rebinding."""
    hosts = set(LOOPBACK_NAMES)
    if bind_host not in WILDCARD_HOSTS:
        hosts.add(bind_host.strip("[]").lower())
    hosts.update(name.strip("[]").lower() for name in extra or [])
    return hosts


def make_handler(office: Office, hosts: set[str] = LOOPBACK_NAMES):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format, *args):  # keep the terminal quiet
            pass

        # The worker can run commands on this machine, so only pages opened by a known name may
        # drive it: a site that points its own domain at this address still sends its own name.
        def _host_allowed(self) -> bool:
            try:
                host = urlsplit(f"//{self.headers.get('Host', '')}").hostname or ""
            except ValueError:
                return False
            return host in hosts

        def _origin_allowed(self) -> bool:
            origin = self.headers.get("Origin")
            return origin is None or urlsplit(origin).netloc == self.headers.get("Host")

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            text = content_type.startswith("text/") or content_type == "application/json"
            self.send_header("Content-Type", f"{content_type}; charset=utf-8" if text else content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data: dict) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode(), "application/json")

        def do_GET(self):
            if not self._host_allowed():
                return self._json(HTTPStatus.FORBIDDEN, {"error": FORBIDDEN_HOST})
            path = urlsplit(self.path).path
            if path == "/api/state":
                return self._json(HTTPStatus.OK, office.snapshot())
            if path == "/api/events":
                return self._events()
            name = "index.html" if path == "/" else path.removeprefix("/static/")
            file = STATIC_DIR / name
            if "/" in name or file.suffix not in STATIC_TYPES or not file.is_file():
                return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            self._send(HTTPStatus.OK, file.read_bytes(), STATIC_TYPES[file.suffix])

        def do_POST(self):
            if not self._host_allowed():
                return self._json(HTTPStatus.FORBIDDEN, {"error": FORBIDDEN_HOST})
            if not self._origin_allowed():
                return self._json(HTTPStatus.FORBIDDEN, {"error": "forbidden origin"})
            # Requiring JSON forces a CORS preflight on cross-site requests, which this server never approves.
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                return self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "expected JSON"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}") if length > 0 else {}
            except ValueError:  # a bad length or bad JSON
                self.close_connection = True
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON"})
            if not isinstance(body, dict):
                return self._json(HTTPStatus.BAD_REQUEST, {"error": "expected a JSON object"})

            actions = {
                "/api/task": lambda: office.start_task(str(body.get("text", ""))),
                "/api/review": office.request_review,
                "/api/rework": office.send_rework,
                "/api/accept": office.accept,
                "/api/stop": lambda: office.stop(str(body.get("agent", "worker"))),
                "/api/ideas": lambda: office.generate_ideas(str(body.get("topic", ""))),
                "/api/handoff": lambda: office.hand_off(body.get("index")),
                "/api/lang": lambda: office.set_language(str(body.get("lang", ""))),
                "/api/autopilot": lambda: office.set_autopilot(
                    body.get("enabled") is True, body.get("max_rounds")
                ),
            }
            action = actions.get(urlsplit(self.path).path)
            if action is None:
                return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            try:
                action()
            except Busy as e:
                return self._json(HTTPStatus.CONFLICT, {"error": str(e)})
            except (ValueError, ContextError) as e:
                return self._json(HTTPStatus.BAD_REQUEST, {"error": str(e)})
            except Exception as e:  # the page should hear about it instead of losing the connection
                print(f"ai-office: {self.path}: {e!r}", file=sys.stderr)
                return self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"server error: {e}"})
            self._json(HTTPStatus.OK, office.snapshot())

        def _events(self):
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            q, backlog = office.subscribe()
            try:
                self._sse({"type": "state", "state": office.snapshot()})
                for entry in backlog:
                    self._sse({"type": "log", "entry": entry})
                while True:
                    try:
                        self._sse(q.get(timeout=HEARTBEAT_SECONDS))
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                office.unsubscribe(q)
                self.close_connection = True

        def _sse(self, event: dict) -> None:
            self.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()

    return Handler


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="ai-office",
        description="Three Claude agents in an office: one comes up with ideas, one writes code, one reviews it.",
    )
    p.add_argument("--workspace", default="workspace", help="project folder the worker edits (default: ./workspace)")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--host", default="127.0.0.1", help="address to listen on (default: 127.0.0.1)")
    p.add_argument(
        "--allow-host",
        action="append",
        default=[],
        metavar="NAME",
        help="another name the page may be opened by, e.g. a Tailscale name (repeatable)",
    )
    p.add_argument("--model", help="Claude model for both agents (default: Claude Code's default)")
    p.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
    p.add_argument("--no-bash", action="store_true", help="do not let the worker run shell commands")
    p.add_argument("--lang", choices=LANGUAGES, default="en", help="language of the page and the agents (default: en)")
    p.add_argument("--no-skills", action="store_true", help="run the agents without the office's skills")
    args = p.parse_args(argv)

    workspace = Path(args.workspace).resolve()
    tools = [t for t in WORKER_TOOLS if not (args.no_bash and t == "Bash")]
    office = Office(
        workspace,
        model=args.model,
        effort=args.effort,
        worker_tools=tools,
        lang=args.lang,
        skills=not args.no_skills,
    )

    hosts = allowed_hosts(args.host, args.allow_host)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(office, hosts))
    server.daemon_threads = True
    print(f"AI office: http://{args.host}:{server.server_port}  (workspace: {workspace})")
    if args.host.strip("[]") not in LOOPBACK_NAMES:
        print("warning: listening beyond this machine; anyone who can reach it can run the worker", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
