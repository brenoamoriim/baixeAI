"""Downloader orchestration through the API (eager Celery). The extractor is injected so these run
without internet; real yt-dlp is covered in tests/engines/test_downloader.py and the verify module."""

import uuid

import pytest
from sqlalchemy import select

from app.models import TermsAcceptance, UrlInspection
from app.security import ssrf
from app.tools.downloader import worker
from app.tools.downloader.extractor import ExtractionError, VideoExtractor, VideoInfo
from tests.conftest import make_user

MP4 = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2" + b"\x00" * 2048
PUBLIC = "93.184.215.14"


class FakeExtractor(VideoExtractor):
    def __init__(self, duration=60.0, fail_with: ExtractionError | None = None, inspect_error=None):
        self.duration = duration
        self.fail_with = fail_with
        self.inspect_error = inspect_error
        self.downloads = []

    def inspect(self, url):
        if self.inspect_error:
            raise self.inspect_error
        return VideoInfo(title="Lançamento", duration_seconds=self.duration, extractor="Fake",
                         heights=[360, 720], has_audio=True, has_video=True, filesize_approx=1000)

    def download(self, url, output, quality, work_dir, progress):
        self.downloads.append((url, output, quality))
        progress(50)
        if self.fail_with:
            raise self.fail_with
        path = work_dir / f"download.{output}"
        path.write_bytes(MP4 if output == "mp4" else b"ID3\x04" + b"\x00" * 2048)
        return path


@pytest.fixture
def fake(monkeypatch):
    extractor = FakeExtractor()
    monkeypatch.setattr(worker, "_override", extractor)
    monkeypatch.setattr(ssrf, "resolve", lambda host, port: (PUBLIC,) if host.endswith(".example") else ("127.0.0.1",))
    return extractor


def _inspect(client, url="https://videos.example/watch/1"):
    return client.post("/api/v1/downloads/inspect", json={"url": url})


def _job(client, inspection, output="mp4", **options):
    return client.post("/api/v1/jobs", headers={"Idempotency-Key": uuid.uuid4().hex}, json={
        "tool_id": "video_downloader", "input_format": "url", "output_format": output,
        "options": {"inspection_id": inspection["id"], **options}})


def _credits(client):
    return client.get("/api/v1/me/credits").json()["total_general"]


@pytest.fixture
def user_client(client):
    client.login(make_user().email)
    return client


@pytest.mark.parametrize("url", ["http://127.0.0.1/v", "http://169.254.169.254/latest/meta-data/", "file:///etc/passwd",
                                 "http://user:pw@videos.example/", "https://videos.example:8443/", "gopher://x"])
def test_unsafe_urls_rejected_before_anything(user_client, fake, db, url):
    r = _inspect(user_client, url)
    assert r.status_code == 400
    assert db.execute(select(UrlInspection)).first() is None and fake.downloads == []


def test_full_flow_charges_once_and_records_rights(user_client, fake, db):
    inspection = _inspect(user_client).json()
    assert inspection["status"] == "ready" and inspection["heights"] == [360, 720]
    estimate = user_client.post("/api/v1/jobs/estimate", json={
        "tool_id": "video_downloader", "input_format": "url", "output_format": "mp4",
        "options": {"inspection_id": inspection["id"], "quality": "720"}}).json()
    assert estimate == {"cost": 1}
    refused = _job(user_client, inspection, quality="720")
    assert refused.status_code == 400 and refused.json()["error"]["code"] == "rights_not_accepted"
    job = _job(user_client, inspection, quality="720", accept_rights=True).json()
    assert job["status"] == "completed", job
    assert fake.downloads == [("https://videos.example/watch/1", "mp4", "720")]
    file = user_client.get(user_client.post(f"/api/v1/jobs/{job['id']}/download-link").json()["url"])
    assert file.content.startswith(MP4[:12]) and "Lan" in file.headers["content-disposition"]
    assert _credits(user_client) == 4
    rows = db.execute(select(TermsAcceptance.document)).scalars().all()
    assert rows == ["video_rights"]


def test_long_video_costs_two(user_client, fake):
    fake.duration = 300.0  # D1: > 2 min
    inspection = _inspect(user_client).json()
    job = _job(user_client, inspection, accept_rights=True).json()
    assert job["credit_cost"] == 2 and _credits(user_client) == 3


def test_quality_that_does_not_exist_is_refused(user_client, fake):
    inspection = _inspect(user_client).json()
    r = _job(user_client, inspection, quality="2160", accept_rights=True)
    assert r.status_code == 400 and _credits(user_client) == 5 and fake.downloads == []


def test_inspection_failure_never_charges(user_client, fake):
    fake.inspect_error = ExtractionError("private_content", "user_input", "Privado.")
    inspection = _inspect(user_client).json()
    assert inspection["status"] == "rejected" and inspection["error_code"] == "private_content"
    r = _job(user_client, inspection, accept_rights=True)
    assert r.status_code == 400 and _credits(user_client) == 5


def test_platform_block_refunds(user_client, fake):
    fake.fail_with = ExtractionError("blocked_by_platform", "system", "bloqueado")
    job = _job(user_client, _inspect(user_client).json(), accept_rights=True).json()
    assert job["status"] == "failed" and job["error_class"] == "system" and _credits(user_client) == 5


def test_redirect_to_internal_address_is_charged_as_user_error(user_client, fake):
    fake.fail_with = ExtractionError("blocked_destination", "user_input", "endereço proibido")
    job = _job(user_client, _inspect(user_client).json(), accept_rights=True).json()
    assert job["status"] == "failed" and job["error_class"] == "user_input" and _credits(user_client) == 4


def test_other_user_cannot_use_inspection(new_client, fake):
    alice, bob = new_client(), new_client()
    alice.login(make_user().email)
    bob.login(make_user().email)
    inspection = _inspect(alice).json()
    assert bob.get(f"/api/v1/downloads/inspections/{inspection['id']}").status_code == 404
    assert _job(bob, inspection, accept_rights=True).status_code == 404 and _credits(bob) == 5


def test_guest_can_download_once(client, fake):
    inspection = _inspect(client).json()
    job = _job(client, inspection, accept_rights=True).json()
    assert job["status"] == "completed" and job["charged_from"] == "guest"


def test_admin_sees_success_rate_per_domain(new_client, fake):
    user, admin = new_client(), new_client()
    user.login(make_user().email)
    _job(user, _inspect(user).json(), accept_rights=True)
    admin.login(make_user(role="admin").email)
    assert user.get("/api/v1/admin/download-stats").status_code == 403
    rows = {r["domain"]: r for r in admin.get("/api/v1/admin/download-stats").json()["domains"]}
    assert rows["videos.example"]["fetch_success_rate"] == 1.0
    assert rows["videos.example"]["counters"]["inspect:ok"] == 1
