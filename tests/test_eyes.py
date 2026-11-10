"""The office's eyes: a page seen through a real browser, and the server a page is shown from."""

import http.client
import socket
import struct
import threading
import time

import pytest

from office import eyes, shot
from office.eyes import DESKTOP, PHONE, LookError, find_browser, look
from office.preview import find_page, serve

needs_browser = pytest.mark.skipif(find_browser() is None, reason="no Chrome, Edge or Chromium on this computer")

GOOD = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Good</title>
<style>body{font-family:sans-serif;margin:24px;background:#fff;color:#111}.tall{height:1700px}</style></head>
<body><h1>Hello</h1><input id="name"><button id="go"
 onclick="document.querySelector('h1').textContent='Hi '+document.getElementById('name').value">Go</button>
<div class="tall">A long page.</div></body></html>"""

BROKEN = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Broken</title>
<style>body{font-family:sans-serif;margin:16px;background:#fff;color:#111}.faint{color:#bbb}
.wide{width:700px}.hero{background:linear-gradient(#000,#333);color:#444}
.scroller{overflow-x:auto}.scroller div{width:900px}</style></head>
<body><h1>Broken</h1><p class="faint">This grey text is too faint.</p>
<div class="hero">Text on a gradient cannot be judged</div>
<div class="scroller"><div>A wide strip in its own scroller is fine</div></div>
<div class="wide" id="table">A block 700px wide</div><img src="missing.png" alt="">
<script>alert('hello'); console.error('something went wrong', 42); notDefined();</script></body></html>"""


def png_size(path):
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    folder = tmp_path_factory.mktemp("pages")
    for name, html in (("good", GOOD), ("broken", BROKEN)):
        (folder / name).mkdir()
        (folder / name / "index.html").write_text(html, encoding="utf-8")
    return folder


@pytest.fixture(autouse=True)
def quick_looks(monkeypatch):
    monkeypatch.setattr(eyes, "SETTLE_SECONDS", 0.1)  # these pages have no animations to wait for


# ---------- looking ----------


@needs_browser
def test_a_good_page_is_photographed_at_both_sizes(pages, tmp_path):
    seen = look(str(pages / "good"), tmp_path / "shots")

    desktop, phone = seen.views
    assert png_size(desktop.shots[0]) == (1280, 800)
    assert png_size(phone.shots[0]) == (780, 1688)  # 390x844 at twice the density, like a phone
    assert seen.problems() == [] and not desktop.faint and not phone.faint
    assert seen.report(tmp_path).splitlines() == [
        "desktop 1280x800", "  shots/desktop.png", "phone 390x844", "  shots/phone.png", "no problems found",
    ]


@needs_browser
def test_a_broken_page_says_what_is_wrong(pages, tmp_path):
    seen = look(str(pages / "broken" / "index.html"), tmp_path)

    problems = seen.problems()
    assert "script error: something went wrong 42" in problems
    assert any(p.startswith("script error: ReferenceError: notDefined is not defined (index.html:") for p in problems)
    assert "failed to load: 404 /missing.png" in problems
    assert "phone: the page is 326px wider than the screen: div#table (326px past the edge)" in problems
    assert not any(p.startswith("desktop: the page is") for p in problems)  # it fits a desktop
    faint = [text for view in seen.views for text in view.faint]
    assert all("p.faint" in text and "has 1.9:1, needs 4.5:1" in text for text in faint) and len(faint) == 2
    assert any("dialog (alert): hello" in note for note in seen.notes)  # and the page did not hang on it
    report = seen.report()
    assert "problems\n  script error:" in report and "hard to read (check by eye)" in report


@needs_browser
def test_steps_act_like_a_visitor(pages, tmp_path):
    steps = ["fill=#name::Ада", "click=#go", "shot=after typing", "eval=document.querySelector('h1').textContent"]
    for device in (PHONE, DESKTOP):  # a tap on the phone, a click on the desktop
        seen = look(str(pages / "good"), tmp_path, devices=(device,), steps=steps)

        assert [s.name for s in seen.views[0].shots] == [f"after-typing-{device.name}.png", f"{device.name}.png"]
        assert seen.notes == ["document.querySelector('h1').textContent -> \"Hi Ада\""]


@needs_browser
def test_a_long_page_is_photographed_a_screen_at_a_time(pages, tmp_path):
    seen = look(str(pages / "good"), tmp_path, devices=(DESKTOP,), full=True)

    assert [s.name for s in seen.views[0].shots] == ["desktop.png", "desktop-2.png", "desktop-3.png"]
    assert all(png_size(s) == (1280, 800) for s in seen.views[0].shots)


@needs_browser
@pytest.mark.parametrize("step, message", [
    ("click=#nope", "no element matches '#nope'"),
    ("dance=now", "unknown step"),
    ("wait=soon", "milliseconds"),
    ("press=Ctrl+Z", "unknown key"),
    ("eval=(() => { throw new Error('boom') })()", "boom"),
])
def test_a_step_that_cannot_be_done_stops_the_look(pages, tmp_path, step, message):
    with pytest.raises(LookError, match=message):
        look(str(pages / "good"), tmp_path, devices=(DESKTOP,), steps=[step])


@needs_browser
def test_a_page_that_does_not_open_is_an_error(tmp_path):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]  # nothing listens here once the socket is closed
    with pytest.raises(LookError, match="could not open"):
        look(f"http://127.0.0.1:{port}/", tmp_path, devices=(DESKTOP,))


def test_no_file_and_no_browser_are_errors(tmp_path, monkeypatch):
    with pytest.raises(LookError, match="no such file or folder"):
        look(str(tmp_path / "missing.html"), tmp_path, browser="/bin/true")
    monkeypatch.setattr(eyes, "find_browser", lambda: None)
    with pytest.raises(LookError, match="No Chrome, Edge or Chromium"):
        look(str(tmp_path), tmp_path)


def test_the_browser_can_be_named(tmp_path, monkeypatch):
    browser = tmp_path / "my-browser"
    browser.write_text("")
    monkeypatch.setenv(eyes.BROWSER_ENV, str(browser))
    assert find_browser() == str(browser)
    monkeypatch.setenv(eyes.BROWSER_ENV, str(tmp_path / "gone"))
    assert find_browser() is None


@needs_browser
def test_the_shot_command_reports_and_fails_clearly(pages, tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(pages / "good")

    assert shot.main(["index.html", "--only", "desktop", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "desktop 1280x800" in out and "no problems found" in out and "Read tool" in out

    assert shot.main(["index.html", "--only", "desktop", "click=#nope"]) == 1
    assert "no element matches" in capsys.readouterr().err
    monkeypatch.setattr(shot, "find_browser", lambda: None)
    assert shot.main(["index.html"]) == 2
    assert "No Chrome, Edge or Chromium" in capsys.readouterr().err


# ---------- the connection to the browser ----------


def test_the_socket_speaks_websocket():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    long = b"x" * 70000
    got = []

    def browser():
        conn, _ = server.accept()
        request = b""
        while b"\r\n\r\n" not in request:
            request += conn.recv(4096)
        got.append(request)
        conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n")
        # A message in two pieces with a ping between them, then one too long for a short frame.
        conn.sendall(bytes([0x01, 3]) + b"hel" + bytes([0x89, 2]) + b"hi" + bytes([0x80, 2]) + b"lo")
        conn.sendall(bytes([0x81, 127]) + struct.pack(">Q", len(long)) + long)
        data = b""
        while len(data) < 8 + 11:  # the pong and the "hello" the client sends, each masked
            data += conn.recv(4096)
        got.append(data)
        conn.close()

    thread = threading.Thread(target=browser, daemon=True)
    thread.start()
    link = eyes._Socket(server.getsockname()[1], "/devtools/browser/1")
    deadline = time.monotonic() + 5

    assert link.receive(deadline) == "hello"
    assert link.receive(deadline) == long.decode()
    link.send("hello")
    thread.join(5)
    link.close()
    server.close()

    def unmasked(frame):
        mask, body = frame[2:6], frame[6:]
        return frame[0], bytes(b ^ mask[n % 4] for n, b in enumerate(body))

    assert b"Upgrade: websocket" in got[0] and b"Origin" not in got[0]
    assert unmasked(got[1][:8]) == (0x8A, b"hi")  # the ping was answered
    assert unmasked(got[1][8:]) == (0x81, b"hello")


# ---------- the page that is served ----------


def test_the_built_page_wins_and_a_page_that_needs_a_bundler_is_not_one(tmp_path):
    assert find_page(tmp_path) is None

    (tmp_path / "index.html").write_text('<div id="root"></div><script type="module" src="/src/main.tsx"></script>')
    assert find_page(tmp_path) is None  # opened as it is, it would show nothing

    (tmp_path / "timer.html").write_text("<h1>Timer</h1>")
    assert find_page(tmp_path) == (tmp_path, "timer.html")

    (tmp_path / "frontend" / "dist").mkdir(parents=True)
    (tmp_path / "frontend" / "dist" / "index.html").write_text("<h1>Built</h1>")
    assert find_page(tmp_path) == (tmp_path / "frontend" / "dist", "index.html")


def test_a_plain_page_in_the_project_or_its_public_folder(tmp_path):
    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "index.html").write_text("<h1>Public</h1>")
    assert find_page(tmp_path) == (tmp_path / "public", "index.html")

    (tmp_path / "index.html").write_text("<h1>Root</h1>")
    assert find_page(tmp_path) == (tmp_path, "index.html")


@pytest.fixture
def site(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<h1>Home</h1>")
    (tmp_path / "assets" / "style.css").write_text("body{}")
    (tmp_path / ".env").write_text("SECRET=1")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]")
    (tmp_path.parent / "outside.txt").write_text("outside")
    server = serve(lambda: tmp_path, hosts={"127.0.0.1"})
    yield server.server_port
    server.shutdown()
    server.server_close()


def fetch(port, path, method="GET", host=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(method, path, headers={"Host": host or f"127.0.0.1:{port}"})
    response = conn.getresponse()
    return response.status, response.getheader("Content-Type"), response.read()


def test_the_preview_serves_the_page_and_nothing_hidden(site):
    assert fetch(site, "/") == (200, "text/html; charset=utf-8", b"<h1>Home</h1>")
    assert fetch(site, "/assets/style.css")[:2] == (200, "text/css; charset=utf-8")
    assert fetch(site, "/about/team")[2] == b"<h1>Home</h1>"  # a route the page handles itself
    assert fetch(site, "/index.html", "HEAD") == (200, "text/html; charset=utf-8", b"")
    for path in ["/.env", "/.git/config", "/..%2foutside.txt", "/assets/..%5c..%5coutside.txt", "/missing.css"]:
        assert fetch(site, path)[0] == 404
    assert fetch(site, "/", host="evil.example")[0] == 403
