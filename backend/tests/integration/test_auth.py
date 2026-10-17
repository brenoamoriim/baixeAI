import re

from sqlalchemy import select

from app.core.config import get_settings
from app.models import AuditEvent, UserSession
from app.services import email
from tests.conftest import PASSWORD, make_user


def _token_from_outbox(path: str) -> str:
    body = next(m.body for m in reversed(email.outbox) if path in m.body)
    return re.search(r"token=([A-Za-z0-9_-]+)", body).group(1)


def test_register_verify_login_logout(client):
    r = client.post("/api/v1/auth/register", json={"email": "Nova@Exemplo.com", "password": PASSWORD})
    assert r.status_code == 202
    assert email.outbox[-1].to == "nova@exemplo.com"

    client.login("nova@exemplo.com")
    assert client.get("/api/v1/me").json()["email_verified"] is False

    token = _token_from_outbox("/verificar-email")
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200
    assert client.get("/api/v1/me").json()["email_verified"] is True
    # single use
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 400

    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/me").status_code == 401


def test_session_cookie_flags(client):
    make_user("flags@exemplo.com")
    r = client.login("flags@exemplo.com")
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert get_settings().session_cookie_name in cookie


def test_session_token_is_stored_hashed(client, db):
    make_user("hash@exemplo.com")
    client.login("hash@exemplo.com")
    raw = client.cookies.get(get_settings().session_cookie_name)
    stored = db.execute(select(UserSession.token_hash)).scalars().all()
    assert raw not in stored and len(stored) == 1 and len(stored[0]) == 64


def test_register_does_not_reveal_existing_email(client):
    make_user("existe@exemplo.com")
    r1 = client.post("/api/v1/auth/register", json={"email": "existe@exemplo.com", "password": PASSWORD})
    r2 = client.post("/api/v1/auth/register", json={"email": "novo@exemplo.com", "password": PASSWORD})
    assert r1.status_code == r2.status_code == 202
    assert r1.json() == r2.json()


def test_login_errors_are_generic_and_audited(client, db):
    make_user("a@exemplo.com")
    wrong = client.post("/api/v1/auth/login", json={"email": "a@exemplo.com", "password": "errada-123456"})
    missing = client.post("/api/v1/auth/login", json={"email": "x@exemplo.com", "password": "errada-123456"})
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json()["error"]["message"] == missing.json()["error"]["message"]
    actions = db.execute(select(AuditEvent.action)).scalars().all()
    assert actions.count("login_failed") == 2


def test_weak_password_rejected(client):
    r = client.post("/api/v1/auth/register", json={"email": "f@exemplo.com", "password": "curta"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "weak_password"


def test_password_reset_revokes_sessions(new_client):
    make_user("reset@exemplo.com")
    device_a, device_b = new_client(), new_client()
    device_a.login("reset@exemplo.com")
    assert device_b.post("/api/v1/auth/forgot-password", json={"email": "reset@exemplo.com"}).status_code == 202
    token = _token_from_outbox("/redefinir-senha")
    r = device_b.post("/api/v1/auth/reset-password", json={"token": token, "password": "nova-senha-forte"})
    assert r.status_code == 200
    assert device_a.get("/api/v1/me").status_code == 401  # signed out everywhere
    device_b.login("reset@exemplo.com", "nova-senha-forte")
    assert device_b.post("/api/v1/auth/login",
                         json={"email": "reset@exemplo.com", "password": PASSWORD}).status_code == 401


def test_forgot_password_unknown_email_same_response(client):
    r = client.post("/api/v1/auth/forgot-password", json={"email": "ninguem@exemplo.com"})
    assert r.status_code == 202 and not email.outbox


def test_login_rate_limited_per_email(client):
    make_user("bruta@exemplo.com")
    codes = [
        client.post("/api/v1/auth/login", json={"email": "bruta@exemplo.com", "password": "errada-000000"}).status_code
        for _ in range(10)
    ]
    assert codes[:8] == [401] * 8 and codes[8:] == [429, 429]


def test_csrf_required_for_unsafe_requests(client):
    make_user("csrf@exemplo.com")
    r = client.post("/api/v1/auth/login", json={"email": "csrf@exemplo.com", "password": PASSWORD},
                    headers={"X-CSRF-Token": "outro-valor"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"


def test_admin_endpoint_requires_admin_role(client):
    make_user("comum@exemplo.com")
    make_user("chefe@exemplo.com", role="admin")
    assert client.get("/api/v1/admin/settings").status_code == 401
    client.login("comum@exemplo.com")
    assert client.get("/api/v1/admin/settings").status_code == 403
    client.post("/api/v1/auth/logout")
    client.login("chefe@exemplo.com")
    r = client.get("/api/v1/admin/settings")
    assert r.status_code == 200 and any(s["key"] == "daily_free_credits" for s in r.json()["settings"])


def test_security_headers_present(client):
    r = client.get("/healthz")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
