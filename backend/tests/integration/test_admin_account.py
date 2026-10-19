import uuid

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import AuditEvent, CreditPackage, Payment, ToolCapability, User, UserSession
from tests.conftest import PASSWORD, make_user

ADMIN_ROUTES = [
    ("GET", "/api/v1/admin/overview"), ("GET", "/api/v1/admin/tools"), ("PATCH", "/api/v1/admin/tools/converter"),
    ("GET", "/api/v1/admin/capabilities?tool_id=converter"), ("PATCH", f"/api/v1/admin/capabilities/{uuid.uuid4()}"),
    ("GET", "/api/v1/admin/cost-rules"), ("PATCH", f"/api/v1/admin/cost-rules/{uuid.uuid4()}"),
    ("GET", "/api/v1/admin/catalog"), ("PATCH", "/api/v1/admin/plans/pro"), ("PATCH", "/api/v1/admin/packages/x"),
    ("GET", "/api/v1/admin/settings"), ("PATCH", "/api/v1/admin/settings/daily_free_credits"),
    ("GET", "/api/v1/admin/flags"), ("PATCH", "/api/v1/admin/flags/ads_enabled"),
    ("GET", "/api/v1/admin/payments"), ("POST", f"/api/v1/admin/payments/{uuid.uuid4()}/refund"),
    ("POST", "/api/v1/admin/payments/reconcile"), ("GET", "/api/v1/admin/subscriptions"),
    ("GET", "/api/v1/admin/audit"), ("GET", "/api/v1/admin/users"),
    ("POST", f"/api/v1/admin/users/{uuid.uuid4()}/suspend"), ("GET", "/api/v1/admin/download-stats"),
]
BODY = {"PATCH": {"enabled": True, "status": "planned", "value": 5}, "POST": {"suspended": True}}


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_every_admin_route_requires_admin(new_client, method, path):
    anon, user = new_client(), new_client()
    user.login(make_user().email)
    for client, expected in ((anon, 401), (user, 403)):
        r = client.request(method, path, json=BODY.get(method))
        assert r.status_code == expected, (path, r.status_code)


@pytest.fixture
def admin(client):
    client.login(make_user(role="admin").email)
    return client


def test_sensitive_change_requires_password_and_is_audited(admin, db):
    r = admin.patch("/api/v1/admin/tools/converter", json={"credit_cost": 3})
    assert r.status_code == 403 and r.json()["error"]["code"] == "reauth_failed"
    r = admin.patch("/api/v1/admin/tools/converter", json={"credit_cost": 3, "confirm_password": "errada-123456"})
    assert r.status_code == 403
    r = admin.patch("/api/v1/admin/tools/converter", json={"credit_cost": 3, "confirm_password": PASSWORD})
    assert r.status_code == 200
    event = db.execute(select(AuditEvent).where(AuditEvent.action == "tool_cost_changed")).scalar_one()
    assert event.metadata_ == {"old": 1, "new": 3} and event.actor_type == "admin"


def test_unverified_capability_cannot_be_made_available(admin, db):
    with SessionLocal() as s, s.begin():
        cap = ToolCapability(tool_id="converter", category="document", input_format="pptx", output_format="pdf",
                             status="planned", engine="libreoffice", options_schema={})
        s.add(cap)
    r = admin.patch(f"/api/v1/admin/capabilities/{cap.id}", json={"status": "available", "confirm_password": PASSWORD})
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_verified"
    verified = db.execute(select(ToolCapability).where(ToolCapability.tool_id == "converter",
                                                       ToolCapability.status == "available")).scalars().first()
    r = admin.patch(f"/api/v1/admin/capabilities/{verified.id}", json={"status": "planned", "confirm_password": PASSWORD})
    assert r.status_code == 200  # taking one out is always allowed
    r = admin.patch(f"/api/v1/admin/capabilities/{verified.id}", json={"status": "available", "confirm_password": PASSWORD})
    assert r.status_code == 200  # back in, because it is verified


def test_price_change_reflects_in_catalog_and_new_checkouts(admin):
    r = admin.patch("/api/v1/admin/packages/pack_converter_10", json={"price_cents": 590, "confirm_password": PASSWORD})
    assert r.status_code == 200
    packs = {p["code"]: p["price_cents"] for p in admin.get("/api/v1/catalog").json()["packages"]}
    assert packs["pack_converter_10"] == 590
    assert admin.patch("/api/v1/admin/packages/pack_converter_10",
                       json={"price_cents": 1, "confirm_password": PASSWORD}).status_code == 400


@pytest.mark.parametrize("key,value", [
    ("limits_bytes", {"image": 1, "document": 1, "audio": 1, "video": 200 * 1024 * 1024}),  # > 95 MB (Cloudflare)
    ("daily_free_credits", -1), ("daily_free_credits", "5"), ("adsense_client_id", "pub-123"),
    ("adsense_slots", {"home": "abc"}), ("secret_key", "x"),
])
def test_settings_are_validated(admin, key, value):
    assert admin.patch(f"/api/v1/admin/settings/{key}", json={"value": value}).status_code == 400


def test_ads_appear_only_when_flag_and_client_are_set(admin):
    assert admin.get("/api/v1/site-config").json()["ads"] == {"enabled": False, "client": None, "slots": {}}
    admin.patch("/api/v1/admin/settings/adsense_client_id", json={"value": "ca-pub-1234567890"})
    config = admin.get("/api/v1/site-config").json()
    assert config["ads"]["enabled"] is False  # flag still off
    assert config["ads_txt_client"] == "ca-pub-1234567890"  # ads.txt must exist before AdSense approval
    admin.patch("/api/v1/admin/settings/adsense_slots", json={"value": {"home_bottom": "111"}})
    admin.patch("/api/v1/admin/flags/ads_enabled", json={"enabled": True})
    assert admin.get("/api/v1/site-config").json()["ads"] == {
        "enabled": True, "client": "ca-pub-1234567890", "slots": {"home_bottom": "111"}}


def test_suspend_revokes_sessions_and_blocks_login(new_client):
    admin, victim = new_client(), new_client()
    admin.login(make_user(role="admin").email)
    target = make_user()
    victim.login(target.email)
    r = admin.post(f"/api/v1/admin/users/{target.id}/suspend", json={"suspended": True, "confirm_password": PASSWORD})
    assert r.status_code == 200
    assert victim.get("/api/v1/me").status_code == 401
    assert victim.post("/api/v1/auth/login", json={"email": target.email, "password": PASSWORD}).status_code == 401


def test_admin_cannot_suspend_self(admin, db):
    me = db.execute(select(User).where(User.role == "admin")).scalar_one()
    r = admin.post(f"/api/v1/admin/users/{me.id}/suspend", json={"suspended": True, "confirm_password": PASSWORD})
    assert r.status_code == 409


def test_audit_and_overview_are_available_to_admin(admin):
    assert "users" in admin.get("/api/v1/admin/overview").json()
    assert isinstance(admin.get("/api/v1/admin/audit").json()["events"], list)


# ---------------------------------------------------------------- account (LGPD)


def test_export_contains_only_own_data(new_client):
    a, b = new_client(), new_client()
    ua, ub = make_user(), make_user()
    a.login(ua.email)
    b.login(ub.email)
    a.create_echo()
    r = a.get("/api/v1/me/export")
    data = r.json()
    assert "attachment" in r.headers["content-disposition"]
    assert data["account"]["email"] == ua.email and len(data["jobs"]) == 1
    assert ub.email not in r.text
    assert b.get("/api/v1/me/export").json()["jobs"] == []


def test_delete_account_anonymizes_and_signs_out(new_client, db):
    c, other = new_client(), new_client()
    user = make_user()
    c.login(user.email)
    other.login(user.email)
    c.create_echo()
    assert c.post("/api/v1/me/delete", json={"password": "errada-123456", "confirm": "EXCLUIR"}).status_code == 403
    assert c.post("/api/v1/me/delete", json={"password": PASSWORD, "confirm": "sim"}).status_code == 422
    assert c.post("/api/v1/me/delete", json={"password": PASSWORD, "confirm": "EXCLUIR"}).status_code == 200
    row = db.get(User, user.id)
    assert row.status == "deleted" and user.email not in row.email and row.email.endswith("@invalid.baixeai")
    assert other.get("/api/v1/me").status_code == 401  # every session revoked
    assert c.post("/api/v1/auth/login", json={"email": user.email, "password": PASSWORD}).status_code == 401
    # the e-mail can be used again for a new account
    assert c.post("/api/v1/auth/register", json={"email": user.email, "password": PASSWORD}).status_code == 202


def test_delete_keeps_financial_records(client, db):
    user = make_user()
    client.login(user.email)
    with SessionLocal() as s, s.begin():
        pack = s.execute(select(CreditPackage).limit(1)).scalar_one()
        s.add(Payment(user_id=user.id, purpose="package", package_id=pack.id, amount_cents=490, status="approved"))
    client.post("/api/v1/me/delete", json={"password": PASSWORD, "confirm": "EXCLUIR"})
    assert db.execute(select(Payment).where(Payment.user_id == user.id)).scalar_one().amount_cents == 490


def test_admin_account_cannot_self_delete(admin):
    assert admin.post("/api/v1/me/delete", json={"password": PASSWORD, "confirm": "EXCLUIR"}).status_code == 400


def test_change_password_keeps_current_session_only(new_client, db):
    here, there = new_client(), new_client()
    user = make_user()
    here.login(user.email)
    there.login(user.email)
    r = here.post("/api/v1/me/password", json={"current_password": "errada-123456", "new_password": "nova-senha-forte"})
    assert r.status_code == 403
    r = here.post("/api/v1/me/password", json={"current_password": PASSWORD, "new_password": "nova-senha-forte"})
    assert r.status_code == 200
    assert here.get("/api/v1/me").status_code == 200 and there.get("/api/v1/me").status_code == 401
    active = db.execute(select(UserSession).where(UserSession.user_id == user.id,
                                                  UserSession.revoked_at.is_(None))).scalars().all()
    assert len(active) == 1


def test_cli_verify_email_is_dev_only(monkeypatch, db):
    from app import cli
    from app.core.config import get_settings

    user = make_user(verified=False)
    cli.main(["verify-email", "--email", user.email])
    db.expire_all()
    assert db.get(User, user.id).email_verified_at is not None

    other = make_user(verified=False)
    monkeypatch.setattr(type(get_settings()), "is_production", property(lambda self: True))
    with pytest.raises(SystemExit):
        cli.main(["verify-email", "--email", other.email])
    db.expire_all()
    assert db.get(User, other.id).email_verified_at is None


def test_session_probe_is_200_for_visitors_and_users(new_client):
    anon, user = new_client(), new_client()
    assert anon.get("/api/v1/me/session").json() == {"user": None}
    u = make_user()
    user.login(u.email)
    assert user.get("/api/v1/me/session").json()["user"]["email"] == u.email
