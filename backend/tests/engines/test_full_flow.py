"""End-to-end through the API with real engines (run inside worker-light / worker-media)."""

import uuid

import pytest
from sqlalchemy import update

from app.core.db import SessionLocal
from app.models import SystemSetting
from tests.conftest import make_user
from tests.engines.conftest import light, media


def _upload(client, name: str, data: bytes):
    return client.post("/api/v1/uploads", files={"file": (name, data, "application/octet-stream")})


def _convert(client, upload: dict, output: str, key: str | None = None, **options):
    return client.post(
        "/api/v1/jobs",
        json={"tool_id": "converter", "input_format": upload["format"], "output_format": output,
              "options": {"upload_id": upload["id"], **options}},
        headers={"Idempotency-Key": key or uuid.uuid4().hex},
    )


def _credits(client) -> int:
    return client.get("/api/v1/me/credits").json()["total_general"]


@pytest.fixture
def user_client(client):
    user = make_user()
    client.login(user.email)
    return client


@light
def test_txt_to_pdf_full_flow(user_client, fixtures):
    data = fixtures["document"]["txt"].read_bytes()
    upload = _upload(user_client, "relatório final.txt", data).json()
    assert upload["status"] == "ready" and upload["format"] == "txt"   # probe ran (eager) before any charge
    assert _credits(user_client) == 5

    estimate = user_client.post("/api/v1/jobs/estimate", json={
        "tool_id": "converter", "input_format": "txt", "output_format": "pdf",
        "options": {"upload_id": upload["id"]}}).json()
    assert estimate == {"cost": 1}

    job = _convert(user_client, upload, "pdf").json()
    assert job["status"] == "completed", job
    assert _credits(user_client) == 4
    link = user_client.post(f"/api/v1/jobs/{job['id']}/download-link").json()["url"]
    file = user_client.get(link)
    assert file.content.startswith(b"%PDF-")
    assert "relatório final.pdf" in file.headers["content-disposition"] or "relat" in file.headers["content-disposition"]


@light
def test_wrong_extension_uses_real_format(user_client, fixtures):
    upload = _upload(user_client, "foto.pdf", fixtures["image"]["png"].read_bytes()).json()
    assert upload["format"] == "png"
    r = _convert(user_client, {**upload, "format": "pdf"}, "docx")
    assert r.status_code in (400, 404) and _credits(user_client) == 5


@light
def test_pixel_bomb_rejected_before_charge(user_client):
    from tests.engines.test_negative import _png_header_only

    upload = _upload(user_client, "bomba.png", _png_header_only(60000, 60000)).json()
    assert upload["status"] == "rejected" and upload["error_code"] == "image_too_large"
    r = _convert(user_client, upload, "jpg")
    assert r.status_code == 400 and r.json()["error"]["code"] == "image_too_large"
    assert _credits(user_client) == 5


@light
def test_file_over_category_limit_is_refused(user_client, fixtures):
    with SessionLocal() as db, db.begin():
        db.execute(update(SystemSetting).where(SystemSetting.key == "limits_bytes").values(
            value={"image": 100, "document": 25_000_000, "audio": 50_000_000, "video": 95_000_000}))
    r = _upload(user_client, "a.png", fixtures["image"]["png"].read_bytes())
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"


@light
def test_corrupted_document_is_charged_per_prd(user_client):
    """Passes the cheap checks but LibreOffice cannot read it -> user_input -> no refund (PRD §2)."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("[Content_Types].xml", "<broken")
        archive.writestr("word/document.xml", "<<<")
    upload = _upload(user_client, "quebrado.docx", buf.getvalue()).json()
    assert upload["status"] == "ready"
    job = _convert(user_client, upload, "pdf").json()
    assert job["status"] == "failed" and job["error_class"] == "user_input"
    assert _credits(user_client) == 4


@light
def test_engine_crash_refunds(user_client, fixtures, monkeypatch):
    from app.tools.base import ToolSystemError
    from app.tools.converter import documents

    def crash(*args, **kwargs):
        raise ToolSystemError("libreoffice_failed")

    monkeypatch.setattr(documents, "convert", crash)
    upload = _upload(user_client, "a.txt", fixtures["document"]["txt"].read_bytes()).json()
    job = _convert(user_client, upload, "pdf").json()
    assert job["status"] == "failed" and job["error_class"] == "system"
    assert _credits(user_client) == 5


@light
def test_retry_with_same_key_is_not_charged_twice(user_client, fixtures):
    upload = _upload(user_client, "a.txt", fixtures["document"]["txt"].read_bytes()).json()
    first = _convert(user_client, upload, "pdf", key="mesma-chave-conversao").json()
    second = _convert(user_client, upload, "pdf", key="mesma-chave-conversao").json()
    assert first["id"] == second["id"] and _credits(user_client) == 4


@light
def test_other_user_cannot_use_or_download(new_client, fixtures):
    alice, bob = new_client(), new_client()
    alice.login(make_user().email)
    bob.login(make_user().email)
    upload = _upload(alice, "a.txt", fixtures["document"]["txt"].read_bytes()).json()
    assert bob.get(f"/api/v1/uploads/{upload['id']}").status_code == 404
    assert _convert(bob, upload, "pdf").status_code == 404           # cannot convert Alice's file
    job = _convert(alice, upload, "pdf").json()
    link = alice.post(f"/api/v1/jobs/{job['id']}/download-link").json()["url"]
    assert bob.get(link).status_code == 404


@light
def test_hostile_svg_converts_without_scripts(user_client):
    svg = (b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="30" onload="alert(1)">'
           b'<script>alert(1)</script><rect width="40" height="30" fill="red"/>'
           b'<image href="http://169.254.169.254/x" width="5" height="5"/></svg>')
    upload = _upload(user_client, "x.svg", svg).json()
    assert upload["status"] == "ready" and upload["info"] == {"width": 40, "height": 30}
    job = _convert(user_client, upload, "png").json()
    assert job["status"] == "completed"


@media
def test_video_conversion_costs_two_and_extract_audio(user_client, fixtures):
    upload = _upload(user_client, "clipe.mp4", fixtures["video"]["mp4"].read_bytes()).json()
    assert upload["status"] == "ready" and upload["info"]["has_audio"] is True
    job = _convert(user_client, upload, "mp3", bitrate="128k").json()
    assert job["status"] == "completed" and job["credit_cost"] == 2   # D1: video category costs 2
    assert _credits(user_client) == 3


@media
def test_audio_only_mp4_is_reclassified_as_m4a(user_client, fixtures):
    upload = _upload(user_client, "musica.mp4", fixtures["audio"]["m4a"].read_bytes()).json()
    assert upload["format"] == "m4a" and upload["category"] == "audio"
    job = _convert(user_client, upload, "mp3").json()
    assert job["status"] == "completed" and job["credit_cost"] == 1


@media
def test_too_long_video_rejected_before_charge(user_client, fixtures):
    with SessionLocal() as db, db.begin():
        db.execute(update(SystemSetting).where(SystemSetting.key == "video_max_seconds").values(value=1))
    upload = _upload(user_client, "longo.mp4", fixtures["video"]["mp4"].read_bytes()).json()
    assert upload["status"] == "rejected" and upload["error_code"] == "too_long"
    assert _credits(user_client) == 5
