"""Payments end to end through the API with a fake provider API.

The fake subclasses the REAL MercadoPago class, so webhook signature verification, timestamp
tolerance and status normalization are the production code; only HTTP calls to Mercado Pago are
replaced by an in-memory "provider state" the tests control (approve, refund, charge...).
"""

import hashlib
import hmac
import threading
import time
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select, update

from app import payments as payments_pkg
from app.core import clock
from app.core.db import SessionLocal
from app.models import AuditEvent, CreditBucket, Payment, PaymentEvent, Plan, Subscription, SystemSetting
from app.payments.mercadopago import MercadoPago
from app.payments.provider import CheckoutSession, ProviderPayment, ProviderSubscription, SubscriptionSession
from app.services import payments as service
from tests.conftest import make_user

SECRET = "test-webhook-secret"


class FakeMP(MercadoPago):
    def __init__(self):
        super().__init__("TEST-token", SECRET)
        self.payments: dict[str, ProviderPayment] = {}
        self.charges: dict[str, str] = {}  # authorized_payment id -> payment id
        self.subscriptions: dict[str, ProviderSubscription] = {}
        self.calls: list[tuple] = []

    def create_checkout(self, *, payment_id, title, amount_cents, payer_email, notification_url, back_url):
        self.calls.append(("checkout", payment_id, amount_cents))
        return CheckoutSession(redirect_url=f"https://mp.test/checkout/{payment_id}", provider_reference=f"pref-{payment_id}")

    def create_subscription(self, *, subscription_id, reason, amount_cents, payer_email, back_url):
        pid = f"pre-{subscription_id[:8]}"
        self.subscriptions[pid] = ProviderSubscription(pid, "pending", subscription_id, amount_cents)
        self.calls.append(("subscription", subscription_id, amount_cents))
        return SubscriptionSession(redirect_url=f"https://mp.test/sub/{pid}", provider_subscription_id=pid)

    def update_subscription_amount(self, provider_subscription_id, amount_cents):
        self.calls.append(("update_amount", provider_subscription_id, amount_cents))

    def cancel_subscription(self, provider_subscription_id):
        self.calls.append(("cancel", provider_subscription_id))

    def get_payment(self, provider_payment_id):
        return self.payments[provider_payment_id]

    def find_payments(self, external_reference):
        return [p for p in self.payments.values() if p.external_reference == external_reference]

    def get_subscription(self, provider_subscription_id):
        return self.subscriptions[provider_subscription_id]

    def get_subscription_charge(self, charge_id):
        return self.payments.get(self.charges.get(charge_id, ""))

    def refund(self, provider_payment_id, amount_cents, idempotency_key):
        self.calls.append(("refund", provider_payment_id, amount_cents, idempotency_key))

    # helpers for tests ------------------------------------------------------------
    def set_payment(self, pid, *, status, amount_cents, ref, method="credit_card", subscription_id=None, refunded=0):
        self.payments[pid] = ProviderPayment(
            provider_payment_id=pid, status=status, status_detail=None, amount_cents=amount_cents, currency="BRL",
            external_reference=ref, method=method, approved_at=clock.now() if status == "approved" else None,
            refunded_cents=refunded, subscription_id=subscription_id, raw_status=status)


@pytest.fixture
def mp():
    fake = FakeMP()
    payments_pkg.set_override(fake)
    yield fake
    payments_pkg.set_override(None)


def _signed_headers(data_id: str, request_id: str | None = None, ts: int | None = None, secret: str = SECRET):
    request_id = request_id or uuid.uuid4().hex
    ts = ts or int(time.time())
    manifest = f"id:{data_id.lower()};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return {"x-signature": f"ts={ts},v1={v1}", "x-request-id": request_id}


def notify(client, topic: str, data_id: str, **kw):
    return client.post(f"/api/webhooks/mercadopago?data.id={data_id}&type={topic}",
                       json={"type": topic, "action": f"{topic}.updated", "data": {"id": data_id}},
                       headers=_signed_headers(data_id, **kw))


def _credits(client):
    return client.get("/api/v1/me/credits").json()


def _plan_credits(client):
    return sum(b["available"] for b in _credits(client)["buckets"] if b["kind"] == "plan")


@pytest.fixture
def buyer(client):
    user = make_user()
    client.login(user.email)
    client.user = user
    return client


def _buy(client, product, mode="manual", **extra):
    r = client.post("/api/v1/checkout", json={"product": product, "mode": mode, **extra})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- catalog & checkout


def test_catalog_prices_come_from_database(client):
    data = client.get("/api/v1/catalog").json()
    prices = {p["code"]: p["price_cents"] for p in data["plans"]}
    assert prices == {"pro": 2490, "premium": 3990, "lifetime": 12000}
    packs = {p["tool_id"]: p["price_cents"] for p in data["packages"]}
    assert packs == {"video_downloader": 990, "converter": 490, "object_remover": 490, "background_remover": 490}
    assert data["lifetime_seats_left"] == 50


def test_tampered_price_from_frontend_is_ignored(buyer, mp):
    out = _buy(buyer, "package:pack_converter_10", amount_cents=1, price=0.01, unit_price=0.01)
    with SessionLocal() as db:
        assert db.get(Payment, uuid.UUID(out["payment_id"])).amount_cents == 490
    assert mp.calls[-1] == ("checkout", out["payment_id"], 490)


def test_payments_disabled_without_credentials(buyer):
    payments_pkg.set_override(None)
    r = buyer.post("/api/v1/checkout", json={"product": "package:pack_converter_10"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "payments_unavailable"


def test_unverified_email_cannot_buy(client, mp):
    client.login(make_user(verified=False).email)
    r = client.post("/api/v1/checkout", json={"product": "package:pack_converter_10"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "email_not_verified"


# ---------------------------------------------------------------- webhook security


@pytest.mark.parametrize("method", ["bank_transfer", "credit_card", "debit_card", "account_money"])  # pix = bank_transfer
def test_approved_payment_grants_exactly_once_for_each_method(buyer, mp, method):
    out = _buy(buyer, "package:pack_converter_10")
    mp.set_payment("111", status="approved", amount_cents=490, ref=out["payment_id"], method=method)
    rid = uuid.uuid4().hex
    assert notify(buyer, "payment", "111", request_id=rid).json() == {"received": True, "duplicate": False}
    assert notify(buyer, "payment", "111", request_id=rid).json()["duplicate"] is True  # same delivery
    assert notify(buyer, "payment", "111").status_code == 200  # new delivery, same payment
    packs = [b for b in _credits(buyer)["buckets"] if b["kind"] == "package"]
    assert [(b["tool_id"], b["available"]) for b in packs] == [("converter", 10)]
    status = buyer.get(f"/api/v1/payments/{out['payment_id']}").json()
    assert status["status"] == "approved" and status["fulfilled"] and status["method"] == method


def test_invalid_signature_is_rejected_and_never_processed(buyer, mp):
    out = _buy(buyer, "package:pack_converter_10")
    mp.set_payment("222", status="approved", amount_cents=490, ref=out["payment_id"])
    r = buyer.post("/api/webhooks/mercadopago?data.id=222&type=payment",
                   json={"type": "payment", "data": {"id": "222"}}, headers=_signed_headers("222", secret="wrong"))
    assert r.status_code == 401
    r = buyer.post("/api/webhooks/mercadopago?data.id=222&type=payment", json={"type": "payment", "data": {"id": "222"}})
    assert r.status_code == 401
    assert not [b for b in _credits(buyer)["buckets"] if b["kind"] == "package"]
    with SessionLocal() as db:
        flags = db.execute(select(PaymentEvent.signature_valid)).scalars().all()
    assert flags == [False, False]


def test_replayed_old_webhook_is_rejected(buyer, mp):
    out = _buy(buyer, "package:pack_converter_10")
    mp.set_payment("333", status="approved", amount_cents=490, ref=out["payment_id"])
    r = notify(buyer, "payment", "333", ts=int(time.time()) - 3600)
    assert r.status_code == 401


def test_signed_body_for_other_resource_does_not_match(buyer, mp):
    """Signature covers data.id: swapping the id in the URL breaks it."""
    headers = _signed_headers("444")
    r = buyer.post("/api/webhooks/mercadopago?data.id=999&type=payment",
                   json={"type": "payment", "data": {"id": "999"}}, headers=headers)
    assert r.status_code == 401


def test_return_redirect_never_grants(buyer, mp):
    out = _buy(buyer, "package:pack_converter_10")
    mp.set_payment("555", status="approved", amount_cents=490, ref=out["payment_id"])
    # user comes back from checkout (no webhook yet): status page only reads our state
    assert buyer.get(f"/api/v1/payments/{out['payment_id']}").json()["fulfilled"] is False
    assert not [b for b in _credits(buyer)["buckets"] if b["kind"] == "package"]


def test_pending_then_approved(buyer, mp):
    out = _buy(buyer, "package:pack_converter_10")
    mp.set_payment("666", status="pending", amount_cents=490, ref=out["payment_id"], method="bank_transfer")
    notify(buyer, "payment", "666")
    assert buyer.get(f"/api/v1/payments/{out['payment_id']}").json()["status"] == "pending"
    mp.set_payment("666", status="approved", amount_cents=490, ref=out["payment_id"], method="bank_transfer")
    notify(buyer, "payment", "666")
    assert buyer.get(f"/api/v1/payments/{out['payment_id']}").json()["fulfilled"] is True


@pytest.mark.parametrize("status", ["rejected", "cancelled"])
def test_rejected_or_cancelled_grants_nothing(buyer, mp, status):
    out = _buy(buyer, "package:pack_converter_10")
    mp.set_payment("667", status=status, amount_cents=490, ref=out["payment_id"])
    notify(buyer, "payment", "667")
    assert buyer.get(f"/api/v1/payments/{out['payment_id']}").json()["status"] == status
    assert not [b for b in _credits(buyer)["buckets"] if b["kind"] == "package"]


def test_amount_mismatch_never_grants(buyer, mp):
    out = _buy(buyer, "package:pack_converter_10")
    mp.set_payment("777", status="approved", amount_cents=1, ref=out["payment_id"])
    notify(buyer, "payment", "777")
    assert not [b for b in _credits(buyer)["buckets"] if b["kind"] == "package"]
    with SessionLocal() as db:
        assert db.execute(select(AuditEvent).where(AuditEvent.action == "payment_mismatch")).first() is not None


def test_concurrent_notifications_grant_once(buyer, mp):
    from app.workers.tasks import _process_event

    out = _buy(buyer, "package:pack_converter_10")
    mp.set_payment("888", status="approved", amount_cents=490, ref=out["payment_id"])
    with SessionLocal() as db, db.begin():
        ids = [db.execute(PaymentEvent.__table__.insert().values(
            provider="mercadopago", dedup_key=f"race-{i}", topic="payment", resource_id="888", signature_valid=True,
            attempts=0, payload={}).returning(PaymentEvent.id)).scalar_one() for i in range(5)]
    barrier = threading.Barrier(5)

    def run(event_id):
        barrier.wait()
        _process_event(event_id)

    threads = [threading.Thread(target=run, args=(i,)) for i in ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with SessionLocal() as db:
        assert db.execute(select(func.count()).select_from(CreditBucket).where(CreditBucket.kind == "package")
                          ).scalar_one() == 1


# ---------------------------------------------------------------- refunds & chargebacks


def test_refund_and_chargeback_revoke_remaining_credits(buyer, mp):
    out = _buy(buyer, "package:pack_converter_10")
    mp.set_payment("901", status="approved", amount_cents=490, ref=out["payment_id"])
    notify(buyer, "payment", "901")
    mp.set_payment("901", status="charged_back", amount_cents=490, ref=out["payment_id"])
    notify(buyer, "payment", "901")
    assert not [b for b in _credits(buyer)["buckets"] if b["kind"] == "package"]
    with SessionLocal() as db:
        assert db.get(Payment, uuid.UUID(out["payment_id"])).status == "charged_back"


def test_admin_refund_is_proportional_to_unused_credits(new_client, mp):
    buyer, admin = new_client(), new_client()
    user = make_user()
    buyer.login(user.email)
    admin.login(make_user(role="admin").email)
    out = _buy(buyer, "package:pack_converter_10")
    mp.set_payment("902", status="approved", amount_cents=490, ref=out["payment_id"])
    notify(buyer, "payment", "902")
    with SessionLocal() as db, db.begin():  # spend 4 of 10
        bucket = db.execute(select(CreditBucket).where(CreditBucket.kind == "package")).scalar_one()
        from app.services import credits

        credits.revoke_bucket(db, bucket, reason="test_spend", amount=4)
    assert buyer.post(f"/api/v1/admin/payments/{out['payment_id']}/refund").status_code == 403
    r = admin.post(f"/api/v1/admin/payments/{out['payment_id']}/refund")
    assert r.json() == {"refunded_cents": 294}  # 6/10 of R$ 4,90
    assert mp.calls[-1] == ("refund", "902", 294, f"refund-{out['payment_id']}")
    assert not [b for b in _credits(buyer)["buckets"] if b["kind"] == "package"]


def test_refund_window_closes_after_7_days(new_client, mp):
    buyer, admin = new_client(), new_client()
    buyer.login(make_user().email)
    admin.login(make_user(role="admin").email)
    out = _buy(buyer, "package:pack_converter_10")
    mp.set_payment("903", status="approved", amount_cents=490, ref=out["payment_id"])
    notify(buyer, "payment", "903")
    with SessionLocal() as db, db.begin():
        db.execute(update(Payment).values(approved_at=clock.now() - timedelta(days=8)))
    r = admin.post(f"/api/v1/admin/payments/{out['payment_id']}/refund")
    assert r.status_code == 409 and r.json()["error"]["code"] == "refund_window_closed"


# ---------------------------------------------------------------- plans


def test_manual_plan_activation_and_early_renewal(buyer, mp):
    out = _buy(buyer, "plan:pro")
    mp.set_payment("p1", status="approved", amount_cents=2490, ref=out["payment_id"], method="bank_transfer")
    notify(buyer, "payment", "p1")
    sub = buyer.get("/api/v1/subscription").json()["subscription"]
    assert sub["plan"] == "pro" and sub["status"] == "active" and sub["renewal_mode"] == "manual"
    assert _plan_credits(buyer) == 300
    renewal = buyer.post("/api/v1/subscription/renew").json()
    mp.set_payment("p2", status="approved", amount_cents=2490, ref=renewal["payment_id"], method="bank_transfer")
    notify(buyer, "payment", "p2")
    with SessionLocal() as db:
        cycles = db.execute(select(func.count()).select_from(Subscription)).scalar_one()
        plan_buckets = db.execute(select(CreditBucket).where(CreditBucket.kind == "plan").order_by(
            CreditBucket.valid_from)).scalars().all()
    assert cycles == 1 and len(plan_buckets) == 2
    assert plan_buckets[1].valid_from == plan_buckets[0].expires_at  # next cycle starts when this one ends


def test_card_subscription_first_charge_renewal_and_plan_change(buyer, mp):
    out = _buy(buyer, "plan:pro", mode="card_auto")
    assert out["redirect_url"].startswith("https://mp.test/sub/")
    with SessionLocal() as db:
        sub = db.get(Subscription, uuid.UUID(out["subscription_id"]))
    pre = sub.provider_preapproval_id
    mp.set_payment("c1", status="approved", amount_cents=2490, ref=out["subscription_id"], subscription_id=pre)
    mp.charges["ap1"] = "c1"
    notify(buyer, "subscription_authorized_payment", "ap1")
    assert buyer.get("/api/v1/subscription").json()["subscription"]["status"] == "active"
    assert _plan_credits(buyer) == 300
    # schedule upgrade: provider amount updated now, effective next charge
    assert buyer.post("/api/v1/subscription/change", json={"plan": "premium"}).status_code == 200
    assert ("update_amount", pre, 3990) in mp.calls
    with SessionLocal() as db, db.begin():  # spend 100 credits, then jump to the end of the cycle
        bucket = db.execute(select(CreditBucket).where(CreditBucket.kind == "plan")).scalar_one()
        from app.services import credits

        credits.revoke_bucket(db, bucket, reason="test_spend", amount=100)
        end = db.get(Subscription, sub.id).current_period_end
    clock.freeze(end + timedelta(minutes=1))
    mp.set_payment("c2", status="approved", amount_cents=3990, ref=out["subscription_id"], subscription_id=pre)
    mp.charges["ap2"] = "c2"
    notify(buyer, "subscription_authorized_payment", "ap2")
    from app.services import credits as credit_service

    credit_service.expire_due_buckets(SessionLocal)
    buyer.login(buyer.user.email)  # a month later the 14-day session has expired
    assert _plan_credits(buyer) == 800 + 200  # D5: leftover summed into the new plan
    assert buyer.get("/api/v1/subscription").json()["subscription"]["plan"] == "premium"


def test_cancel_keeps_access_until_period_end(buyer, mp):
    out = _buy(buyer, "plan:pro", mode="card_auto")
    with SessionLocal() as db:
        pre = db.get(Subscription, uuid.UUID(out["subscription_id"])).provider_preapproval_id
    mp.set_payment("c3", status="approved", amount_cents=2490, ref=out["subscription_id"], subscription_id=pre)
    mp.charges["ap3"] = "c3"
    notify(buyer, "subscription_authorized_payment", "ap3")
    assert buyer.post("/api/v1/subscription/cancel").status_code == 200
    assert ("cancel", pre) in mp.calls
    assert _plan_credits(buyer) == 300  # still usable
    with SessionLocal() as db:
        end = db.get(Subscription, uuid.UUID(out["subscription_id"])).current_period_end
    service.subscription_maintenance(SessionLocal, mp, at=end + timedelta(minutes=1))
    with SessionLocal() as db:
        assert db.get(Subscription, uuid.UUID(out["subscription_id"])).status == "expired"


def test_card_grace_period_then_expiry(buyer, mp):
    out = _buy(buyer, "plan:pro", mode="card_auto")
    with SessionLocal() as db:
        pre = db.get(Subscription, uuid.UUID(out["subscription_id"])).provider_preapproval_id
    mp.set_payment("c4", status="approved", amount_cents=2490, ref=out["subscription_id"], subscription_id=pre)
    mp.charges["ap4"] = "c4"
    notify(buyer, "subscription_authorized_payment", "ap4")
    sid = uuid.UUID(out["subscription_id"])
    with SessionLocal() as db:
        end = db.get(Subscription, sid).current_period_end
    service.subscription_maintenance(SessionLocal, mp, at=end + timedelta(hours=1))
    with SessionLocal() as db:
        assert db.get(Subscription, sid).status == "past_due"
    service.subscription_maintenance(SessionLocal, mp, at=end + timedelta(days=3, hours=1))
    with SessionLocal() as db:
        assert db.get(Subscription, sid).status == "expired"
    assert ("cancel", pre) in mp.calls


def test_late_card_charge_within_grace_reactivates(buyer, mp):
    out = _buy(buyer, "plan:pro", mode="card_auto")
    sid = uuid.UUID(out["subscription_id"])
    with SessionLocal() as db:
        pre = db.get(Subscription, sid).provider_preapproval_id
    mp.set_payment("c5", status="approved", amount_cents=2490, ref=out["subscription_id"], subscription_id=pre)
    mp.charges["ap5"] = "c5"
    notify(buyer, "subscription_authorized_payment", "ap5")
    with SessionLocal() as db:
        end = db.get(Subscription, sid).current_period_end
    service.subscription_maintenance(SessionLocal, mp, at=end + timedelta(hours=1))
    clock.freeze(end + timedelta(days=1))
    mp.set_payment("c6", status="approved", amount_cents=2490, ref=out["subscription_id"], subscription_id=pre)
    mp.charges["ap6"] = "c6"
    notify(buyer, "subscription_authorized_payment", "ap6")
    with SessionLocal() as db:
        sub = db.get(Subscription, sid)
        assert sub.status == "active" and sub.current_period_start == end + timedelta(days=1)


# ---------------------------------------------------------------- lifetime


def test_lifetime_purchase_replaces_monthly_plan_and_seats_run_out(buyer, mp):
    plan = _buy(buyer, "plan:pro")
    mp.set_payment("l0", status="approved", amount_cents=2490, ref=plan["payment_id"])
    notify(buyer, "payment", "l0")
    out = _buy(buyer, "lifetime")
    mp.set_payment("l1", status="approved", amount_cents=12000, ref=out["payment_id"])
    notify(buyer, "payment", "l1")
    assert _credits(buyer)["lifetime"] is True
    assert buyer.get("/api/v1/subscription").json()["subscription"]["cancel_at_period_end"] is True
    assert buyer.post("/api/v1/checkout", json={"product": "lifetime"}).status_code == 409  # already lifetime
    with SessionLocal() as db, db.begin():
        db.execute(update(SystemSetting).where(SystemSetting.key == "lifetime_max_seats").values(value=1))
    other = make_user()
    buyer.post("/api/v1/auth/logout")
    buyer.login(other.email)
    r = buyer.post("/api/v1/checkout", json={"product": "lifetime"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "lifetime_sold_out"


def test_lifetime_refund_revokes_access(new_client, mp):
    buyer, admin = new_client(), new_client()
    buyer.login(make_user().email)
    admin.login(make_user(role="admin").email)
    out = _buy(buyer, "lifetime")
    mp.set_payment("l2", status="approved", amount_cents=12000, ref=out["payment_id"])
    notify(buyer, "payment", "l2")
    assert admin.post(f"/api/v1/admin/payments/{out['payment_id']}/refund").json() == {"refunded_cents": 12000}
    assert _credits(buyer)["lifetime"] is False


# ---------------------------------------------------------------- reconciliation


def test_reconciliation_recovers_a_lost_webhook(buyer, mp):
    out = _buy(buyer, "package:pack_converter_10")
    mp.set_payment("r1", status="approved", amount_cents=490, ref=out["payment_id"])  # webhook never arrives
    result = service.reconcile(SessionLocal, mp, at=clock.now() + timedelta(minutes=10))
    assert result["applied"] == 1 and result["approved_not_fulfilled"] == []
    assert buyer.get(f"/api/v1/payments/{out['payment_id']}").json()["fulfilled"] is True


def test_unknown_payment_is_audited_not_granted(buyer, mp):
    mp.set_payment("x1", status="approved", amount_cents=490, ref=str(uuid.uuid4()))
    assert notify(buyer, "payment", "x1").status_code == 200
    with SessionLocal() as db:
        assert db.execute(select(AuditEvent).where(AuditEvent.action == "payment_unknown")).first() is not None
        assert db.execute(select(func.count()).select_from(CreditBucket).where(CreditBucket.kind == "package")
                          ).scalar_one() == 0


def test_history_lists_only_own_payments(new_client, mp):
    a, b = new_client(), new_client()
    a.login(make_user().email)
    b.login(make_user().email)
    out = _buy(a, "package:pack_converter_10")
    mp.set_payment("h1", status="approved", amount_cents=490, ref=out["payment_id"])
    notify(a, "payment", "h1")
    assert [p["id"] for p in a.get("/api/v1/payments").json()["payments"]] == [out["payment_id"]]
    assert b.get("/api/v1/payments").json()["payments"] == []
    assert b.get(f"/api/v1/payments/{out['payment_id']}").status_code == 404


def test_plans_listed_in_db(db):
    assert {p.code for p in db.execute(select(Plan)).scalars()} >= {"pro", "premium", "lifetime"}
