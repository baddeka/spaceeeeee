"""Files the user hands the agents: kept in the workspace, outside the project."""

import base64
import json

import pytest

from office import agents
from office import server as office_server
from office.agents import UPLOADS_DIR, Office, safe_file_name

from .test_office import fake_claude, request, server  # noqa: F401 (fixtures)

JSON = {"Content-Type": "application/json"}


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def test_an_upload_is_kept_without_replacing_another(tmp_path):
    office = Office(tmp_path / "ws")

    first = office.save_upload("design.png", b64(b"one"))
    second = office.save_upload("design.png", b64(b"two"))

    folder = tmp_path / "ws" / UPLOADS_DIR
    assert (first, second) == ("design.png", "design (2).png")
    assert (folder / first).read_bytes() == b"one" and (folder / second).read_bytes() == b"two"


@pytest.mark.parametrize(
    "name, saved",
    [("../../etc/passwd", "passwd"), ("C:\\Users\\x\\plan.pdf", "plan.pdf"), ("a<b>:c?.png", "a_b__c_.png"),
     ("CON.txt", "_CON.txt"), ("..", "file"), ("", "file"), ("Макет.pdf", "Макет.pdf")],
)
def test_upload_names_stay_inside_the_folder(name, saved):
    assert safe_file_name(name) == saved


def test_uploads_must_be_readable_and_not_too_big(tmp_path, monkeypatch):
    office = Office(tmp_path / "ws")
    with pytest.raises(ValueError):
        office.save_upload("x.txt", "not base64!")
    monkeypatch.setattr(agents, "MAX_UPLOAD_BYTES", 3)
    with pytest.raises(ValueError):
        office.save_upload("x.txt", b64(b"four"))


def test_the_developer_gets_the_attached_files(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    name = office.save_upload("design.png", b64(b"\x89PNG"))

    office.start_task("Make the page look like the design", files=[name])
    office.wait_idle()

    prompt = fake_claude()[0]["prompt"]
    assert f"- {tmp_path / 'ws' / UPLOADS_DIR / name}" in prompt
    assert "Read tool" in prompt
    assert "📎 design.png" in office._log[0]["text"]


def test_the_idea_maker_gets_the_attached_files(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    name = office.save_upload("brief.pdf", b64(b"%PDF"))

    office.generate_ideas("the hackathon brief", files=[name])
    office.wait_idle()

    assert f"- {tmp_path / 'ws' / UPLOADS_DIR / name}" in fake_claude()[0]["prompt"]


@pytest.mark.parametrize("files", [["missing.png"], ["../app.py"], "design.png", [1]])
def test_a_task_names_only_uploaded_files(tmp_path, files):
    office = Office(tmp_path / "ws")
    (tmp_path / "ws" / "app.py").write_text("x = 1\n")

    with pytest.raises(ValueError):
        office.start_task("x", files=files)
    assert office.agents["worker"]["status"] == "idle"


def test_uploads_are_never_committed_or_reviewed(fake_claude, tmp_path):
    office = Office(tmp_path / "ws")
    name = office.save_upload("secret-brief.pdf", b64(b"%PDF"))
    office.start_task("x", files=[name])
    office.wait_idle()
    office.request_review()
    office.wait_idle()
    office.accept()

    assert ".rens-office" not in office._git("ls-files")
    review = next(c for c in fake_claude() if "--json-schema" in c["args"])
    assert "secret-brief" not in review["prompt"]


def test_http_upload_then_task(server, fake_claude):  # noqa: F811
    base, office = server

    status, body = request(base + "/api/upload", "POST", {"name": "logo.svg", "data": b64(b"<svg/>")}, JSON)
    assert status == 200 and json.loads(body) == {"name": "logo.svg"}
    status, _ = request(base + "/api/task", "POST", {"text": "Use the logo", "files": ["logo.svg"]}, JSON)
    office.wait_idle()

    assert status == 200
    assert "logo.svg" in fake_claude()[0]["prompt"]
    assert request(base + "/api/upload", "POST", {"name": "x", "data": "%%%"}, JSON)[0] == 400


def test_http_refuses_a_body_that_is_too_big(server, monkeypatch):  # noqa: F811
    base, _ = server
    monkeypatch.setattr(office_server, "MAX_BODY_BYTES", 100)

    status, _ = request(base + "/api/upload", "POST", {"name": "x", "data": b64(b"x" * 200)}, JSON)

    assert status == 413
