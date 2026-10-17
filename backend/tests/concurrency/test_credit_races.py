"""Real concurrency against PostgreSQL (docs/architecture/09 §2). Each thread has its own
connection; a barrier releases them at the same instant."""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select, update

from app.core import clock
from app.core.db import SessionLocal
from app.core.errors import AppError
from app.models import CreditBucket, CreditLedger, CreditReservation, ProcessingJob
from app.services import credits, jobs
from app.services.jobs import Actor
from tests.conftest import make_user

pytestmark = pytest.mark.concurrency
N = 20


def _parallel(fn, n=N):
    barrier = threading.Barrier(n)

    def worker(i):
        barrier.wait()
        try:
            return ("ok", fn(i))
        except AppError as exc:
            return ("refused", exc.code)

    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(worker, range(n)))


def _create(user_id, key):
    with SessionLocal() as db:
        job, _ = jobs.create_job(db, Actor(user_id=user_id), tool_id="echo", input_format="text",
                                 output_format="txt", options={"text": "x"}, idempotency_key=key)
        return job.id


@pytest.fixture(autouse=True)
def _no_dispatch(monkeypatch):
    monkeypatch.setattr(jobs, "dispatch", lambda db, job: None)  # measure reservations only
    with SessionLocal() as db, db.begin():
        from app.models import SystemSetting

        db.execute(update(SystemSetting).where(SystemSetting.key == "max_pending_jobs_per_user")
                   .values(value=100))


def _set_daily_balance(user, amount):
    with SessionLocal() as db, db.begin():
        locked = credits.lock_user(db, user.id)
        bucket = credits.ensure_daily_bucket(db, locked, clock.now())
        assert bucket is not None
    # spend down to `amount` through the normal path so the ledger stays consistent
    for _ in range(5 - amount):
        _create(user.id, uuid.uuid4().hex)


def _ledger_ok():
    with SessionLocal() as db:
        assert credits.ledger_mismatches(db) == []


def test_last_credit_spent_exactly_once_under_race():
    user = make_user()
    _set_daily_balance(user, 1)
    results = _parallel(lambda i: _create(user.id, f"race-{i}-{uuid.uuid4().hex}"))
    ok = [r for r in results if r[0] == "ok"]
    refused = [r for r in results if r[0] == "refused"]
    assert len(ok) == 1, results
    assert len(refused) == N - 1 and {code for _, code in refused} == {"insufficient_credits"}
    with SessionLocal() as db:
        bucket = db.execute(select(CreditBucket)).scalar_one()
        assert (bucket.available, bucket.reserved) == (0, 5)
    _ledger_ok()


def test_same_idempotency_key_in_parallel_creates_one_job():
    user = make_user()
    results = _parallel(lambda i: _create(user.id, "mesma-chave-paralela"))
    assert {r[0] for r in results} == {"ok"}
    assert len({job_id for _, job_id in results}) == 1
    with SessionLocal() as db:
        assert db.execute(select(func.count()).select_from(ProcessingJob)).scalar_one() == 1
        assert db.execute(select(func.count()).select_from(CreditReservation)).scalar_one() == 1
    _ledger_ok()


def test_concurrent_commit_and_release_only_one_wins():
    user = make_user()
    job_id = _create(user.id, uuid.uuid4().hex)
    with SessionLocal() as db:
        res_id = db.execute(select(CreditReservation.id).where(CreditReservation.job_id == job_id)).scalar_one()

    def settle(i):
        with SessionLocal() as db, db.begin():
            credits.lock_user(db, user.id)
            if i % 2:
                return "commit" if credits.commit(db, res_id, at=clock.now()) else None
            return "release" if credits.release(db, res_id, at=clock.now(), reason="t") else None

    winners = [r for _, r in _parallel(settle) if r]
    assert len(winners) == 1
    with SessionLocal() as db:
        types = db.execute(select(CreditLedger.entry_type).where(
            CreditLedger.reservation_id == res_id)).scalars().all()
    assert sorted(types) in (["commit", "reserve"], ["release", "reserve"])
    _ledger_ok()


def test_concurrent_first_access_of_the_day_creates_one_daily_bucket():
    user = make_user()

    def read_balance(i):
        with SessionLocal() as db, db.begin():
            return credits.balance(db, user, clock.now())["total_general"]

    results = _parallel(read_balance)
    assert {r for _, r in results} == {5}
    with SessionLocal() as db:
        assert db.execute(select(func.count()).select_from(CreditBucket)).scalar_one() == 1
    _ledger_ok()


def test_concurrent_package_grants_for_same_payment_grant_once():
    from sqlalchemy import text

    from app.models import CreditPackage

    user = make_user(verified=False)
    payment_id = uuid.uuid4()
    with SessionLocal() as db, db.begin():
        db.execute(text(
            "INSERT INTO payments (id, user_id, purpose, amount_cents, currency, provider, status, "
            "refunded_amount_cents) VALUES (:id, :u, 'package', 490, 'BRL', 'mercadopago', 'approved', 0)"),
            {"id": payment_id, "u": user.id})
        package_id = db.execute(select(CreditPackage.id).limit(1)).scalar_one()

    def grant(i):
        with SessionLocal() as db, db.begin():
            credits.lock_user(db, user.id)
            package = db.get(CreditPackage, package_id)
            return credits.grant_package(db, user.id, package, at=clock.now(), payment_id=payment_id) is not None

    results = [r for _, r in _parallel(grant, n=5)]
    assert results.count(True) == 1
    with SessionLocal() as db:
        assert db.execute(select(func.sum(CreditBucket.available))).scalar_one() == 10
    _ledger_ok()


def test_many_parallel_spends_never_go_negative():
    user = make_user()
    results = _parallel(lambda i: _create(user.id, uuid.uuid4().hex))
    assert sum(1 for r in results if r[0] == "ok") == 5
    with SessionLocal() as db:
        bucket = db.execute(select(CreditBucket)).scalar_one()
        assert bucket.available == 0 and bucket.reserved == 5
    _ledger_ok()
