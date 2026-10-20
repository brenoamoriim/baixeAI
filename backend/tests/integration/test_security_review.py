"""Phase 6 security review: authorization policy for every route, IDOR matrix, mass assignment, upload names.

The route policy test fails when a new endpoint is added without being classified here, so access control
is a conscious decision for every route, not an accident.
"""

import uuid
from datetime import timedelta

import pytest
from fastapi.routing import APIRoute

from app.core import clock
from app.core.db import SessionLocal
from app.models import Payment, Upload, UrlInspection, User
from tests.conftest import PASSWORD, make_user

PUBLIC = {
    ("GET", "/api/v1/auth/csrf"), ("POST", "/api/v1/auth/register"), ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/logout"), ("POST", "/api/v1/auth/verify-email"), ("POST", "/api/v1/auth/forgot-password"),
    ("POST", "/api/v1/auth/reset-password"), ("GET", "/api/v1/tools"), ("GET", "/api/v1/catalog"),
    ("GET", "/api/v1/site-config"), ("GET", "/api/v1/me/session"),
    ("POST", "/api/webhooks/mercadopago"),  # authenticated by HMAC signature, not by session
    ("GET", "/healthz"), ("GET", "/readyz"),
}
# Visitors allowed (guest cookie); ownership enforced per resource.
USER_OR_GUEST = {
    ("POST", "/api/v1/uploads"), ("GET", "/api/v1/uploads/{upload_id}"), ("POST", "/api/v1/downloads/inspect"),
    ("GET", "/api/v1/downloads/inspections/{inspection_id}"), ("POST", "/api/v1/jobs/estimate"),
    ("POST", "/api/v1/jobs"), ("GET", "/api/v1/jobs"), ("GET", "/api/v1/jobs/{job_id}"),
    ("POST", "/api/v1/jobs/{job_id}/download-link"), ("GET", "/api/v1/jobs/{job_id}/download"),
}
USER = {
    ("POST", "/api/v1/auth/resend-verification"), ("GET", "/api/v1/me"), ("GET", "/api/v1/me/credits"),
    ("POST", "/api/v1/me/password"), ("GET", "/api/v1/me/export"), ("POST", "/api/v1/me/delete"),
    ("POST", "/api/v1/checkout"), ("GET", "/api/v1/payments"), ("GET", "/api/v1/payments/{payment_id}"),
    ("GET", "/api/v1/subscription"), ("POST", "/api/v1/subscription/cancel"),
    ("POST", "/api/v1/subscription/change"), ("POST", "/api/v1/subscription/renew"),
}


def _routes():
    from app.main import app

    for item in app.routes:
        if isinstance(item, APIRoute):
            yield item, item.path
        elif hasattr(item, "original_router"):  # FastAPI >= 0.140 wraps included routers
            prefix = getattr(item.include_context, "prefix", "")
            for r in item.original_router.routes:
                if isinstance(r, APIRoute):
                    yield r, prefix + r.path


def _deps(dependant, acc):
    for d in dependant.dependencies:
        acc.add(getattr(d.call, "__name__", ""))
        _deps(d, acc)
    return acc


def test_every_route_is_classified_and_guarded_accordingly():
    seen = set()
    for route, path in _routes():
        deps = _deps(route.dependant, set())
        for method in route.methods - {"HEAD", "OPTIONS"}:
            key = (method, path)
            seen.add(key)
            if path.startswith("/api/v1/admin/"):
                assert "require_admin" in deps, key
            elif key in USER:
                assert "current_user" in deps, key
            elif key in USER_OR_GUEST:
                assert "current_user_optional" in deps, key
            else:
                assert key in PUBLIC, f"unclassified route {key}: add it to the policy consciously"
    # the policy lists no stale routes either
    assert (PUBLIC | USER | USER_OR_GUEST) <= seen


def _owned_rows(owner: User) -> dict:
    expires = clock.now() + timedelta(hours=1)
    with SessionLocal() as db, db.begin():
        upload = Upload(owner_user_id=owner.id, storage_key=f"uploads/{uuid.uuid4().hex}", original_name="a.png",
                        format="png", category="image", size_bytes=10, status="ready", meta={}, expires_at=expires)
        inspection = UrlInspection(owner_user_id=owner.id, url="https://example.com/v", domain="example.com",
                                   status="ready", meta={}, expires_at=expires)
        payment = Payment(user_id=owner.id, purpose="package", amount_cents=990, status="approved")
        db.add_all([upload, inspection, payment])
        db.flush()
        return {"upload": upload.id, "inspection": inspection.id, "payment": payment.id}


def test_idor_matrix_other_users_resources_look_missing(new_client):
    owner, intruder, guest = new_client(), new_client(), new_client()
    a = make_user()
    owner.login(a.email)
    intruder.login(make_user().email)
    ids = _owned_rows(a)
    paths = [f"/api/v1/uploads/{ids['upload']}", f"/api/v1/downloads/inspections/{ids['inspection']}"]
    for path in paths:
        assert owner.get(path).status_code == 200, path
        for other in (intruder, guest):
            r = other.get(path)
            assert r.status_code == 404, (path, r.status_code)  # same answer as "does not exist": no oracle
    pay = f"/api/v1/payments/{ids['payment']}"
    assert owner.get(pay).status_code == 200
    assert intruder.get(pay).status_code == 404
    assert guest.get(pay).status_code == 401
    assert intruder.get(f"/api/v1/payments/{uuid.uuid4()}").status_code == 404


def test_mass_assignment_cannot_create_admin_or_preverified(client, db):
    email = f"mass-{uuid.uuid4().hex[:6]}@exemplo.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "role": "admin",
                                                    "email_verified_at": "2020-01-01T00:00:00Z", "status": "active"})
    assert r.status_code == 202, r.text  # neutral answer (no e-mail enumeration)
    user = db.query(User).filter(User.email == email).one()
    assert user.role == "user" and user.email_verified_at is None


def _tiny_png() -> bytes:
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    signature = bytes([0x89]) + b"PNG" + bytes([13, 10, 26, 10])
    pixel = zlib.compress(bytes([0, 255, 0, 0]))
    return signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", pixel) + chunk(b"IEND", b"")


def test_upload_name_cannot_escape_storage(client, db):
    client.login(make_user().email)
    png = _tiny_png()
    for name in ("../../../etc/passwd.png", "..\\..\\windows\\a.png", "/abs/path.png", "a\x00b.png"):
        r = client.post("/api/v1/uploads", files={"file": (name, png, "image/png")})
        assert r.status_code == 201, r.text
        body = r.json()
        assert not any(ch in body["original_name"] for ch in ("/", "\\", "\x00")), body["original_name"]
        row = db.get(Upload, uuid.UUID(body["id"]))
        assert ".." not in row.storage_key and name not in row.storage_key


@pytest.mark.parametrize(
    "method,path", [("PATCH", "/api/v1/admin/tools/converter"), ("POST", "/api/v1/admin/payments/reconcile")]
)
def test_admin_mutations_need_csrf_even_for_admins(new_client, method, path):
    c = new_client()
    c.login(make_user(role="admin").email)
    del c.headers["X-CSRF-Token"]
    assert c.request(method, path, json={"enabled": True}).status_code == 403


def test_suspended_admin_loses_access_immediately(new_client, db):
    c = new_client()
    admin = make_user(role="admin")
    c.login(admin.email)
    assert c.get("/api/v1/admin/overview").status_code == 200
    with SessionLocal() as s, s.begin():
        s.get(User, admin.id).status = "suspended"
    assert c.get("/api/v1/admin/overview").status_code == 401


# ---------------------------------------------------------------- outcomes from (less trusted) engine workers


@pytest.fixture
def pending_job(client, monkeypatch):
    """A job accepted and charged (reserved) but not executed yet: the engine outcome is what we inject."""
    from types import SimpleNamespace

    from app.workers import tasks

    monkeypatch.setattr(tasks.execute_job, "apply_async", lambda *a, **k: SimpleNamespace(id=None))
    client.login(make_user().email)
    job = client.create_echo().json()
    assert job["status"] == "queued"
    return uuid.UUID(job["id"])


def _credits(client) -> int:
    return client.get("/api/v1/me/credits").json()["total_general"]


@pytest.mark.parametrize("forged", [
    {"ok": True, "key": "jobs/00000000000000000000000000000000/x.txt", "filename": "x.txt"},  # other job's file
    {"ok": True, "key": "../../etc/passwd", "filename": "x"},
    {"ok": True, "key": None},
])
def test_forged_engine_success_is_rejected_and_refunded(client, pending_job, forged):
    from app.services import jobs

    with SessionLocal() as db:
        jobs.finish_engine(db, pending_job, forged)
    body = client.get(f"/api/v1/jobs/{pending_job}").json()
    assert body["status"] == "failed" and body["error_class"] == "system"
    assert _credits(client) == 5  # system failure -> reservation released


def test_unknown_error_class_from_engine_becomes_system_failure(client, pending_job):
    from app.services import jobs

    with SessionLocal() as db:
        jobs.finish_engine(db, pending_job, {"ok": False, "error_class": "free_credits", "error_code": "x" * 500})
    body = client.get(f"/api/v1/jobs/{pending_job}").json()
    assert body["error_class"] == "system" and len(body["error_code"]) <= 60


def test_engine_outcome_applies_once(client, pending_job):
    from app.services import jobs

    for _ in range(2):  # redelivered outcome
        with SessionLocal() as db:
            jobs.finish_engine(db, pending_job, {"ok": False, "error_class": "user_input", "error_code": "bad_file"})
    assert _credits(client) == 4  # charged exactly once


def test_probe_result_with_unknown_format_is_rejected(db):
    from app.services import uploads

    owner = make_user()
    with SessionLocal() as s, s.begin():
        up = Upload(owner_user_id=owner.id, storage_key=f"uploads/{uuid.uuid4().hex}", original_name="a.png",
                    format="png", category="image", size_bytes=1, status="probing", meta={},
                    expires_at=clock.now() + timedelta(hours=1))
        s.add(up)
        s.flush()
        upload_id = up.id
    with SessionLocal() as s:
        uploads.apply_probe(s, upload_id, {"ok": True, "format": "exe", "meta": {}})
    db.expire_all()
    assert db.get(Upload, upload_id).status == "rejected"
