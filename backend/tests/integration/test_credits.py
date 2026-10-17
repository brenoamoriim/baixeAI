import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core import clock
from app.core.db import SessionLocal
from app.core.errors import InsufficientCredits
from app.models import (
    CreditBucket,
    CreditLedger,
    CreditPackage,
    Plan,
    ProcessingJob,
    Subscription,
    ToolCapability,
)
from app.services import credits
from tests.conftest import make_user

# 2026-10-17 12:00 in São Paulo (UTC-3)
NOON = datetime(2026, 10, 17, 15, 0, tzinfo=UTC)


def _job(db, user_id) -> uuid.UUID:
    cap = db.execute(select(ToolCapability).where(ToolCapability.tool_id == "echo")).scalar_one()
    job = ProcessingJob(id=uuid.uuid4(), user_id=user_id, tool_id="echo", capability_id=cap.id,
                        status="queued", charged_from="credits", credit_cost=1,
                        idempotency_key=uuid.uuid4().hex, queue="default")
    db.add(job)
    db.flush()
    return job.id


def _reserve(user, amount=1, tool_id="echo", at=NOON):
    with SessionLocal() as db, db.begin():
        locked = credits.lock_user(db, user.id)
        job_id = _job(db, user.id)
        res = credits.reserve(db, locked, tool_id=tool_id, amount=amount, job_id=job_id,
                              idempotency_key=uuid.uuid4().hex, at=at)
        return res.id


def _balance(user, at=NOON) -> dict:
    with SessionLocal() as db, db.begin():
        data = credits.balance(db, user, at)
    return data


def _available(user, at=NOON, kind=None) -> int:
    return sum(b.available for b in _balance(user, at)["buckets"] if kind in (None, b.kind))


def _subscribe(user, plan_code="pro", start=NOON) -> Subscription:
    with SessionLocal() as db, db.begin():
        plan = db.execute(select(Plan).where(Plan.code == plan_code)).scalar_one()
        sub = Subscription(user_id=user.id, plan_id=plan.id, kind="recurring", status="active",
                           renewal_mode="admin")
        db.add(sub)
        db.flush()
        credits.start_plan_cycle(db, sub, period_start=start, at=start)
        return sub


def _assert_ledger_consistent():
    with SessionLocal() as db:
        assert credits.ledger_mismatches(db) == []


# ---------------------------------------------------------------- daily


def test_daily_grant_is_lazy_and_once_per_day():
    user = make_user()
    assert _available(user) == 5
    assert _available(user) == 5  # second read does not grant again
    with SessionLocal() as db:
        assert db.execute(select(CreditBucket).where(CreditBucket.kind == "daily")).scalars().all().__len__() == 1


def test_daily_resets_at_midnight_sao_paulo_without_accumulating():
    user = make_user()
    late = datetime(2026, 10, 18, 2, 59, tzinfo=UTC)  # 23:59 on the 17th in SP
    for _ in range(3):
        _reserve(user, at=late)
    assert _available(user, at=late) == 2
    midnight = datetime(2026, 10, 18, 3, 0, tzinfo=UTC)  # 00:00 on the 18th in SP
    assert _available(user, at=midnight) == 5  # fresh 5, leftover 2 not added
    _assert_ledger_consistent()


def test_unverified_email_gets_no_daily_credits():
    user = make_user(verified=False)
    assert _available(user) == 0
    with pytest.raises(InsufficientCredits):
        _reserve(user)


def test_cannot_spend_more_than_available():
    user = make_user()
    for _ in range(5):
        _reserve(user)
    with pytest.raises(InsufficientCredits):
        _reserve(user)
    _assert_ledger_consistent()


# ---------------------------------------------------------------- plans


def test_subscriber_gets_plan_credits_and_no_daily():
    user = make_user()
    _subscribe(user, "pro")
    balance = _balance(user)
    assert [b.kind for b in balance["buckets"]] == ["plan"]
    assert balance["total_general"] == 300


def test_plan_credits_expire_at_cycle_end_and_do_not_accumulate():
    user = make_user()
    sub = _subscribe(user, "pro")
    for _ in range(10):
        _reserve(user)
    end = clock.add_months(NOON, 1)
    with SessionLocal() as db, db.begin():
        credits.start_plan_cycle(db, db.get(Subscription, sub.id), period_start=end, at=end)
    credits.expire_due_buckets(SessionLocal, at=end)
    assert _available(user, at=end, kind="plan") == 300  # not 590
    _assert_ledger_consistent()


def test_plan_change_carries_leftover_into_new_plan():
    user = make_user()
    sub = _subscribe(user, "pro")
    for _ in range(180):
        _reserve(user)  # 120 left
    with SessionLocal() as db, db.begin():
        premium = db.execute(select(Plan).where(Plan.code == "premium")).scalar_one()
        db.get(Subscription, sub.id).next_plan_id = premium.id
    end = clock.add_months(NOON, 1)
    with SessionLocal() as db, db.begin():
        credits.start_plan_cycle(db, db.get(Subscription, sub.id), period_start=end, at=end)
    assert _available(user, at=end, kind="plan") == 920  # 800 + 120 (D5)
    _assert_ledger_consistent()


def test_early_renewal_with_plan_change_carries_at_expiry():
    user = make_user()
    sub = _subscribe(user, "premium")
    for _ in range(100):
        _reserve(user)  # 700 left
    end = clock.add_months(NOON, 1)
    with SessionLocal() as db, db.begin():
        pro = db.execute(select(Plan).where(Plan.code == "pro")).scalar_one()
        s = db.get(Subscription, sub.id)
        s.next_plan_id = pro.id
        # renewal paid 3 days before the end: next cycle starts at the end
        credits.start_plan_cycle(db, s, period_start=end, at=end - timedelta(days=3))
    assert _available(user, at=end - timedelta(days=1), kind="plan") == 700  # old cycle still running
    credits.expire_due_buckets(SessionLocal, at=end)
    assert _available(user, at=end, kind="plan") == 1000  # 300 + 700
    _assert_ledger_consistent()


# ---------------------------------------------------------------- packages & order


def _grant_package(user, tool_id="echo", at=NOON):
    with SessionLocal() as db, db.begin():
        package = CreditPackage(id=uuid.uuid4(), code=f"pack_{uuid.uuid4().hex[:6]}", tool_id=tool_id,
                                credits=10, price_cents=490, validity_days=90)
        db.add(package)
        db.flush()
        credits.lock_user(db, user.id)
        credits.grant_package(db, user.id, package, at=at)


def test_package_credits_only_for_purchased_tool():
    user = make_user(verified=False)  # no daily credits
    _grant_package(user, tool_id="converter")
    with pytest.raises(InsufficientCredits):
        _reserve(user, tool_id="echo")
    _reserve(user, tool_id="converter")


def test_consumption_order_daily_then_plan_then_package():
    user = make_user()
    _grant_package(user)
    for _ in range(5):
        _reserve(user)
    assert _available(user, kind="daily") == 0 and _available(user, kind="package") == 10
    _reserve(user)
    assert _available(user, kind="package") == 9


def test_subscriber_spends_plan_before_package():
    user = make_user()
    _subscribe(user)
    _grant_package(user)
    _reserve(user)
    assert _available(user, kind="plan") == 299 and _available(user, kind="package") == 10


def test_package_expires_after_90_days():
    user = make_user(verified=False)
    _grant_package(user)
    assert _available(user, at=NOON + timedelta(days=89)) == 10
    assert credits.expire_due_buckets(SessionLocal, at=NOON + timedelta(days=90)) == 1
    assert _available(user, at=NOON + timedelta(days=90)) == 0
    _assert_ledger_consistent()


def test_package_grant_is_idempotent_per_payment():
    user = make_user()
    payment_id = uuid.uuid4()
    with SessionLocal() as db, db.begin():
        db.execute(text(
            "INSERT INTO payments (id, user_id, purpose, amount_cents, currency, provider, status, refunded_amount_cents) "
            "VALUES (:id, :u, 'package', 490, 'BRL', 'mercadopago', 'approved', 0)"), {"id": payment_id, "u": user.id})
        package = db.execute(select(CreditPackage).limit(1)).scalar_one()
        assert credits.grant_package(db, user.id, package, at=NOON, payment_id=payment_id) is not None
        assert credits.grant_package(db, user.id, package, at=NOON, payment_id=payment_id) is None


# ---------------------------------------------------------------- reserve / commit / release


def test_release_returns_credit_and_commit_is_final():
    user = make_user()
    res1, res2 = _reserve(user), _reserve(user)
    with SessionLocal() as db, db.begin():
        assert credits.release(db, res1, at=NOON, reason="system")
        assert not credits.release(db, res1, at=NOON, reason="system")  # idempotent
        assert credits.commit(db, res2, at=NOON)
        assert not credits.release(db, res2, at=NOON, reason="system")  # cannot refund a commit
    assert _available(user) == 4
    _assert_ledger_consistent()


def test_release_after_bucket_expired_grants_compensation():
    user = make_user()
    late = datetime(2026, 10, 18, 2, 59, 59, tzinfo=UTC)
    res = _reserve(user, at=late)
    after = datetime(2026, 10, 18, 3, 0, 5, tzinfo=UTC)
    credits.expire_due_buckets(SessionLocal, at=after)
    with SessionLocal() as db, db.begin():
        credits.release(db, res, at=after, reason="system")
    kinds = {b.kind: b.available for b in _balance(user, at=after)["buckets"]}
    assert kinds["compensation"] == 1 and kinds["daily"] == 5
    _assert_ledger_consistent()


# ---------------------------------------------------------------- ledger protection


def test_ledger_is_append_only():
    user = make_user()
    _reserve(user)
    with pytest.raises(DBAPIError, match="append-only"):
        with SessionLocal() as db, db.begin():
            db.execute(text("UPDATE credit_ledger SET delta_available = 100"))
    with pytest.raises(DBAPIError, match="append-only"):
        with SessionLocal() as db, db.begin():
            db.execute(text("DELETE FROM credit_ledger"))


def test_database_refuses_negative_balance_even_with_buggy_code():
    user = make_user()
    _available(user)
    with pytest.raises(IntegrityError):
        with SessionLocal() as db, db.begin():
            db.execute(text("UPDATE credit_buckets SET available = -1"))


def test_ledger_rows_record_origin_of_each_debit():
    user = make_user()
    _grant_package(user)
    for _ in range(6):
        _reserve(user)
    with SessionLocal() as db:
        rows = db.execute(
            select(CreditBucket.kind, CreditLedger.delta_available)
            .join(CreditBucket, CreditBucket.id == CreditLedger.bucket_id)
            .where(CreditLedger.entry_type == "reserve")
        ).all()
    assert [k for k, _ in rows].count("daily") == 5 and [k for k, _ in rows].count("package") == 1
