"""Credit ("ficha") core: grants, reservation -> commit/release, expiry, balances.

Concurrency model (docs/architecture/04 §4): every operation that changes a user's credits
runs inside a transaction that first locks the user's row (`lock_user`). Lock order is always
user -> job -> reservation -> buckets, which avoids deadlocks. CHECK constraints in the
database are the last line of defense against negative balances.

All functions here expect to run inside a transaction managed by the caller.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import InsufficientCredits
from app.models import (
    CreditBucket,
    CreditLedger,
    CreditPackage,
    CreditReservation,
    CreditReservationItem,
    Plan,
    Subscription,
    SubscriptionCycle,
    User,
)
from app.services.settings import get_setting


def lock_user(db: Session, user_id: uuid.UUID) -> User:
    return db.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one()


def _ledger(
    db: Session,
    bucket: CreditBucket,
    entry_type: str,
    delta_available: int,
    delta_reserved: int,
    reason: str,
    *,
    reservation_id: uuid.UUID | None = None,
    payment_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    actor: str = "system",
) -> None:
    db.add(
        CreditLedger(
            user_id=bucket.user_id,
            bucket_id=bucket.id,
            entry_type=entry_type,
            delta_available=delta_available,
            delta_reserved=delta_reserved,
            reservation_id=reservation_id,
            payment_id=payment_id,
            job_id=job_id,
            actor=actor,
            reason=reason,
        )
    )


# --------------------------------------------------------------------------- entitlements


def active_recurring(db: Session, user_id: uuid.UUID, at: datetime) -> Subscription | None:
    return db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.kind == "recurring",
            Subscription.status == "active",
            Subscription.current_period_end > at,
        )
    ).scalar_one_or_none()


def has_lifetime(db: Session, user_id: uuid.UUID) -> bool:
    return (
        db.execute(
            select(Subscription.id).where(
                Subscription.user_id == user_id,
                Subscription.kind == "lifetime",
                Subscription.status == "active",
            )
        ).first()
        is not None
    )


# --------------------------------------------------------------------------- grants


def _new_bucket(
    db: Session,
    *,
    user_id: uuid.UUID,
    kind: str,
    period_key: str,
    amount: int,
    valid_from: datetime,
    expires_at: datetime,
    tool_id: str | None = None,
    payment_id: uuid.UUID | None = None,
    cycle_id: uuid.UUID | None = None,
) -> CreditBucket | None:
    """Insert a bucket idempotently (UNIQUE user/kind/period_key). Returns None if it existed."""
    bucket_id = uuid.uuid4()
    inserted = db.execute(
        pg_insert(CreditBucket)
        .values(
            id=bucket_id,
            user_id=user_id,
            kind=kind,
            tool_id=tool_id,
            source_payment_id=payment_id,
            subscription_cycle_id=cycle_id,
            period_key=period_key,
            granted=amount,
            available=amount,
            reserved=0,
            valid_from=valid_from,
            expires_at=expires_at,
            status="active",
        )
        .on_conflict_do_nothing(index_elements=["user_id", "kind", "period_key"])
        .returning(CreditBucket.id)
    ).scalar_one_or_none()
    if inserted is None:
        return None
    return db.get(CreditBucket, bucket_id)


def ensure_daily_bucket(db: Session, user: User, at: datetime) -> CreditBucket | None:
    """Lazy daily grant (no reset cron). Subscribers get no daily credits (D3b)."""
    if user.status != "active":
        return None
    if get_setting(db, "require_verified_email_for_credits") and user.email_verified_at is None:
        return None
    if active_recurring(db, user.id, at) is not None or has_lifetime(db, user.id):
        return None
    day = clock.local_date(at)
    start, end = clock.local_day_bounds(day)
    amount = int(get_setting(db, "daily_free_credits"))
    bucket = _new_bucket(
        db,
        user_id=user.id,
        kind="daily",
        period_key=day.isoformat(),
        amount=amount,
        valid_from=start,
        expires_at=end,
    )
    if bucket is not None:
        _ledger(db, bucket, "grant", amount, 0, "daily_free")
    return bucket


def grant_package(
    db: Session,
    user_id: uuid.UUID,
    package: CreditPackage,
    *,
    at: datetime,
    payment_id: uuid.UUID | None = None,
    actor: str = "system",
) -> CreditBucket | None:
    """Grant a tool-scoped package. Idempotent per payment (period_key = payment id)."""
    period_key = str(payment_id) if payment_id else f"admin:{uuid.uuid4()}"
    bucket = _new_bucket(
        db,
        user_id=user_id,
        kind="package",
        period_key=period_key,
        amount=package.credits,
        valid_from=at,
        expires_at=at + timedelta(days=package.validity_days),
        tool_id=package.tool_id,
        payment_id=payment_id,
    )
    if bucket is not None:
        _ledger(db, bucket, "grant", package.credits, 0, f"package:{package.code}",
                payment_id=payment_id, actor=actor)
    return bucket


def _carryover_target(db: Session, bucket: CreditBucket) -> CreditBucket | None:
    """Plan bucket of the next cycle, if the plan changed between cycles (D5)."""
    if bucket.kind != "plan" or bucket.subscription_cycle_id is None:
        return None
    cycle = db.get(SubscriptionCycle, bucket.subscription_cycle_id)
    next_cycle = db.execute(
        select(SubscriptionCycle).where(
            SubscriptionCycle.subscription_id == cycle.subscription_id,
            SubscriptionCycle.cycle_number == cycle.cycle_number + 1,
        )
    ).scalar_one_or_none()
    if next_cycle is None or next_cycle.plan_id == cycle.plan_id:
        return None
    return db.execute(
        select(CreditBucket)
        .where(CreditBucket.subscription_cycle_id == next_cycle.id, CreditBucket.kind == "plan")
        .with_for_update()
    ).scalar_one_or_none()


def start_plan_cycle(
    db: Session,
    subscription: Subscription,
    *,
    period_start: datetime,
    at: datetime,
    payment_id: uuid.UUID | None = None,
    actor: str = "system",
) -> SubscriptionCycle:
    """Open the next billing cycle and grant its plan bucket.

    A scheduled plan change (`next_plan_id`) takes effect here. Leftover credits of the previous
    cycle are carried into the new bucket only when the plan changed (D5); the carry happens when
    the previous bucket expires (now, if it is already past its end; otherwise later, in
    `expire_due_buckets`).
    """
    lock_user(db, subscription.user_id)
    previous = db.execute(
        select(SubscriptionCycle)
        .where(SubscriptionCycle.subscription_id == subscription.id)
        .order_by(SubscriptionCycle.cycle_number.desc())
        .limit(1)
    ).scalar_one_or_none()

    plan_id = subscription.next_plan_id or subscription.plan_id
    plan = db.get(Plan, plan_id)
    period_end = clock.add_months(period_start, 1)
    cycle = SubscriptionCycle(
        subscription_id=subscription.id,
        plan_id=plan.id,
        cycle_number=(previous.cycle_number + 1) if previous else 1,
        period_start=period_start,
        period_end=period_end,
        payment_id=payment_id,
    )
    db.add(cycle)
    db.flush()

    bucket = _new_bucket(
        db,
        user_id=subscription.user_id,
        kind="plan",
        period_key=str(cycle.id),
        amount=plan.credits_per_cycle,
        valid_from=period_start,
        expires_at=period_end,
        payment_id=payment_id,
        cycle_id=cycle.id,
    )
    _ledger(db, bucket, "grant", plan.credits_per_cycle, 0, f"plan_cycle:{plan.code}",
            payment_id=payment_id, actor=actor)

    subscription.plan_id = plan.id
    subscription.next_plan_id = None
    subscription.status = "active"
    subscription.current_period_start = period_start
    subscription.current_period_end = period_end

    if previous is not None and previous.plan_id != plan.id:
        prev_bucket = db.execute(
            select(CreditBucket)
            .where(CreditBucket.subscription_cycle_id == previous.id)
            .with_for_update()
        ).scalar_one_or_none()
        if prev_bucket is not None:
            if prev_bucket.status == "active" and prev_bucket.expires_at <= at:
                _expire_bucket(db, prev_bucket, at)
            elif prev_bucket.status == "expired":
                already_expired = -int(
                    db.execute(
                        select(func.coalesce(func.sum(CreditLedger.delta_available), 0)).where(
                            CreditLedger.bucket_id == prev_bucket.id,
                            CreditLedger.entry_type == "expire",
                        )
                    ).scalar_one()
                )
                _carry_into(db, bucket, already_expired, prev_bucket.id)
    db.flush()
    return cycle


def _carry_into(db: Session, target: CreditBucket, amount: int, source_id: uuid.UUID) -> None:
    if amount <= 0:
        return
    target.granted += amount
    target.available += amount
    _ledger(db, target, "grant", amount, 0, f"plan_change_carryover:{source_id}")


# --------------------------------------------------------------------------- consumption


@dataclass
class BucketView:
    id: uuid.UUID
    kind: str
    tool_id: str | None
    available: int
    reserved: int
    expires_at: datetime


def _eligible_buckets(
    db: Session, user_id: uuid.UUID, tool_id: str, at: datetime, *, lock: bool
) -> list[CreditBucket]:
    stmt = select(CreditBucket).where(
        CreditBucket.user_id == user_id,
        CreditBucket.status == "active",
        CreditBucket.valid_from <= at,
        CreditBucket.expires_at > at,
        CreditBucket.available > 0,
        or_(CreditBucket.tool_id.is_(None), CreditBucket.tool_id == tool_id),
    )
    if lock:
        stmt = stmt.with_for_update()
    buckets = list(db.execute(stmt).scalars())
    order = list(get_setting(db, "credit_consumption_order"))
    priority = {kind: index for index, kind in enumerate(order)}
    buckets.sort(key=lambda b: (priority.get(b.kind, len(order)), b.expires_at, b.created_at))
    return buckets


def reserve(
    db: Session,
    user: User,
    *,
    tool_id: str,
    amount: int,
    job_id: uuid.UUID,
    idempotency_key: str,
    at: datetime,
) -> CreditReservation:
    """Reserve `amount` credits for a job. Caller must hold the user lock (`lock_user`)."""
    ensure_daily_bucket(db, user, at)
    buckets = _eligible_buckets(db, user.id, tool_id, at, lock=True)
    if sum(b.available for b in buckets) < amount:
        raise InsufficientCredits(
            "Você não tem fichas suficientes para esta operação.",
        )
    reservation = CreditReservation(
        id=uuid.uuid4(),
        user_id=user.id,
        job_id=job_id,
        idempotency_key=idempotency_key,
        amount=amount,
        status="reserved",
    )
    db.add(reservation)
    db.flush()
    remaining = amount
    for bucket in buckets:
        if remaining == 0:
            break
        take = min(bucket.available, remaining)
        bucket.available -= take
        bucket.reserved += take
        db.add(CreditReservationItem(reservation_id=reservation.id, bucket_id=bucket.id, amount=take))
        _ledger(db, bucket, "reserve", -take, take, "job_reserve",
                reservation_id=reservation.id, job_id=job_id)
        remaining -= take
    db.flush()
    return reservation


def _locked_reservation(db: Session, reservation_id: uuid.UUID) -> CreditReservation:
    return db.execute(
        select(CreditReservation).where(CreditReservation.id == reservation_id).with_for_update()
    ).scalar_one()


def _items_with_buckets(
    db: Session, reservation_id: uuid.UUID
) -> list[tuple[CreditReservationItem, CreditBucket]]:
    rows = db.execute(
        select(CreditReservationItem, CreditBucket)
        .join(CreditBucket, CreditBucket.id == CreditReservationItem.bucket_id)
        .where(CreditReservationItem.reservation_id == reservation_id)
        .order_by(CreditBucket.id)
        .with_for_update(of=CreditBucket)
    ).all()
    return [(item, bucket) for item, bucket in rows]


def commit(db: Session, reservation_id: uuid.UUID, *, at: datetime) -> bool:
    """Confirm a reservation (job succeeded, or user-input failure). Idempotent."""
    reservation = _locked_reservation(db, reservation_id)
    if reservation.status != "reserved":
        return False
    for item, bucket in _items_with_buckets(db, reservation_id):
        bucket.reserved -= item.amount
        _ledger(db, bucket, "commit", 0, -item.amount, "job_commit",
                reservation_id=reservation.id, job_id=reservation.job_id)
    reservation.status = "committed"
    reservation.resolved_at = at
    db.flush()
    return True


def release(db: Session, reservation_id: uuid.UUID, *, at: datetime, reason: str) -> bool:
    """Return reserved credits (system failure / timeout). Idempotent.

    If the source bucket already expired, the credit is returned and immediately expired, and
    a 24h `compensation` bucket with the same scope is granted (docs/architecture/05 §6).
    """
    reservation = _locked_reservation(db, reservation_id)
    if reservation.status != "reserved":
        return False
    for item, bucket in _items_with_buckets(db, reservation_id):
        bucket.reserved -= item.amount
        bucket.available += item.amount
        _ledger(db, bucket, "release", item.amount, -item.amount, f"job_release:{reason}",
                reservation_id=reservation.id, job_id=reservation.job_id)
        if bucket.status != "active" or bucket.expires_at <= at:
            bucket.available -= item.amount
            _ledger(db, bucket, "expire", -item.amount, 0, "expired_before_release",
                    reservation_id=reservation.id, job_id=reservation.job_id)
            hours = int(get_setting(db, "compensation_validity_hours"))
            compensation = _new_bucket(
                db,
                user_id=bucket.user_id,
                kind="compensation",
                period_key=f"{reservation.id}:{bucket.id}",
                amount=item.amount,
                valid_from=at,
                expires_at=at + timedelta(hours=hours),
                tool_id=bucket.tool_id,
            )
            if compensation is not None:
                _ledger(db, compensation, "grant", item.amount, 0, "compensation",
                        reservation_id=reservation.id, job_id=reservation.job_id)
    reservation.status = "released"
    reservation.resolved_at = at
    db.flush()
    return True


# --------------------------------------------------------------------------- expiry


def _expire_bucket(db: Session, bucket: CreditBucket, at: datetime) -> None:
    leftover = bucket.available
    if leftover:
        bucket.available = 0
        _ledger(db, bucket, "expire", -leftover, 0, "validity_ended")
    bucket.status = "expired"
    target = _carryover_target(db, bucket)
    if target is not None:
        _carry_into(db, target, leftover, bucket.id)


def expire_due_buckets(db_factory, at: datetime | None = None) -> int:
    """Expire buckets past `expires_at`. One short transaction per bucket (user lock first)."""
    at = at or clock.now()
    with db_factory() as db:
        due = db.execute(
            select(CreditBucket.id, CreditBucket.user_id).where(
                CreditBucket.status == "active", CreditBucket.expires_at <= at
            )
        ).all()
    count = 0
    for bucket_id, user_id in due:
        with db_factory() as db, db.begin():
            lock_user(db, user_id)
            bucket = db.execute(
                select(CreditBucket).where(CreditBucket.id == bucket_id).with_for_update()
            ).scalar_one()
            if bucket.status == "active" and bucket.expires_at <= at:
                _expire_bucket(db, bucket, at)
                count += 1
    return count


# --------------------------------------------------------------------------- refunds / chargebacks


def revoke_bucket(db: Session, bucket: CreditBucket, *, reason: str, payment_id: uuid.UUID | None = None,
                  actor: str = "system", amount: int | None = None) -> int:
    """Compensating entry (never edits history): remove up to `amount` available credits (default:
    all). Credits already spent stay spent; the caller audits the shortfall. Returns removed amount."""
    take = bucket.available if amount is None else min(amount, bucket.available)
    if take > 0:
        bucket.available -= take
        _ledger(db, bucket, "revoke", -take, 0, reason, payment_id=payment_id, actor=actor)
    if amount is None and bucket.reserved == 0:
        bucket.status = "revoked"
    db.flush()
    return take


# --------------------------------------------------------------------------- reads


def balance(db: Session, user: User, at: datetime) -> dict:
    """Current balance by origin. Creates today's daily bucket lazily (needs user lock)."""
    lock_user(db, user.id)
    ensure_daily_bucket(db, user, at)
    rows = db.execute(
        select(CreditBucket)
        .where(
            CreditBucket.user_id == user.id,
            CreditBucket.status == "active",
            CreditBucket.valid_from <= at,
            CreditBucket.expires_at > at,
            or_(CreditBucket.available > 0, CreditBucket.reserved > 0),
        )
        .order_by(CreditBucket.expires_at)
    ).scalars()
    buckets = [
        BucketView(b.id, b.kind, b.tool_id, b.available, b.reserved, b.expires_at) for b in rows
    ]
    return {
        "lifetime": has_lifetime(db, user.id),
        "buckets": buckets,
        "total_general": sum(b.available for b in buckets if b.tool_id is None),
    }


def ledger_mismatches(db: Session) -> list[uuid.UUID]:
    """Buckets whose materialized counters differ from the ledger sums (should be empty)."""
    sums = (
        select(
            CreditLedger.bucket_id.label("bucket_id"),
            func.sum(CreditLedger.delta_available).label("avail"),
            func.sum(CreditLedger.delta_reserved).label("res"),
        )
        .group_by(CreditLedger.bucket_id)
        .subquery()
    )
    rows = db.execute(
        select(CreditBucket.id)
        .outerjoin(sums, sums.c.bucket_id == CreditBucket.id)
        .where(
            or_(
                func.coalesce(sums.c.avail, 0) != CreditBucket.available,
                func.coalesce(sums.c.res, 0) != CreditBucket.reserved,
                and_(sums.c.bucket_id.is_(None)),
            )
        )
    ).scalars()
    return list(rows)
