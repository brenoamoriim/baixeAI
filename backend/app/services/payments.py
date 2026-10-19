"""Payments business rules (PRD §3-§5). Knows nothing about the Mercado Pago SDK/API shape.

Invariants:
- prices come from the database catalog and are snapshotted on the payment row; nothing from the
  client is trusted (the frontend only says WHICH product);
- credit/plan is granted only after the provider API (not the webhook body, not the redirect) says
  `approved`, with matching amount, currency and reference; exactly once (row lock + fulfilled_at +
  unique constraints);
- refunds/chargebacks are compensating ledger entries; history is never edited.
"""

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.errors import AppError, Conflict, NotFound
from app.models import (
    AuditEvent,
    CreditBucket,
    CreditPackage,
    Payment,
    Plan,
    Subscription,
    SubscriptionCycle,
    ToolDefinition,
    User,
)
from app.payments.provider import PaymentProvider, ProviderPayment, ProviderSubscription
from app.services import credits
from app.services.settings import get_setting

log = logging.getLogger(__name__)
LIFETIME_HOLD = timedelta(minutes=30)  # an open lifetime checkout holds a seat for 30 min


def _audit(db: Session, action: str, *, actor: str = "system", target: str | None = None, **meta) -> None:
    db.add(
        AuditEvent(
            actor_type="system" if actor == "system" else "user",
            actor_id=actor if actor != "system" else None,
            action=action,
            target_type="payment",
            target_id=target,
            metadata_=meta,
        )
    )


def _urls(payment_or_sub_id: str) -> tuple[str, str]:
    settings = get_settings()
    api = (settings.api_public_url or settings.app_base_url).rstrip("/")
    return (
        f"{api}/api/webhooks/mercadopago",
        f"{settings.app_base_url.rstrip('/')}/pagamento/retorno?ref={payment_or_sub_id}",
    )


# =========================================================================== catalog


def catalog(db: Session) -> dict:
    plans = db.execute(select(Plan).where(Plan.active.is_(True)).order_by(Plan.price_cents)).scalars().all()
    packages = db.execute(
        select(CreditPackage, ToolDefinition)
        .join(ToolDefinition, ToolDefinition.id == CreditPackage.tool_id)
        .where(CreditPackage.active.is_(True), ToolDefinition.dev_only.is_(False))
        .order_by(CreditPackage.price_cents.desc())
    ).all()
    return {
        "plans": [
            {
                "code": p.code,
                "name": p.name,
                "kind": p.kind,
                "price_cents": p.price_cents,
                "credits_per_cycle": p.credits_per_cycle,
            }
            for p in plans
            if p.kind != "free"
        ],
        "packages": [
            {
                "code": pk.code,
                "tool_id": pk.tool_id,
                "tool_name": tool.package_display_name,
                "credits": pk.credits,
                "price_cents": pk.price_cents,
                "validity_days": pk.validity_days,
            }
            for pk, tool in packages
        ],
        "lifetime_seats_left": lifetime_seats_left(db),
    }


def lifetime_seats_left(db: Session) -> int | None:
    seats = get_setting(db, "lifetime_max_seats")
    if seats is None:
        return 0
    sold = db.execute(
        select(func.count())
        .select_from(Subscription)
        .where(Subscription.kind == "lifetime", Subscription.status == "active")
    ).scalar_one()
    held = db.execute(
        select(func.count())
        .select_from(Payment)
        .where(
            Payment.purpose == "lifetime",
            Payment.status.in_(("created", "pending")),
            Payment.created_at > clock.now() - LIFETIME_HOLD,
        )
    ).scalar_one()
    return max(int(seats) - sold - held, 0)


# =========================================================================== start purchase


def _require_buyer(user: User) -> None:
    if user.email_verified_at is None:
        raise AppError("Confirme seu e-mail antes de comprar.", code="email_not_verified")


def _plan(db: Session, code: str, kind: str) -> Plan:
    plan = db.execute(
        select(Plan).where(Plan.code == code, Plan.kind == kind, Plan.active.is_(True))
    ).scalar_one_or_none()
    if plan is None:
        raise NotFound("Plano indisponível.", code="product_not_found")
    return plan


def start_checkout(db: Session, provider: PaymentProvider, user: User, product: str, mode: str = "manual") -> dict:
    """Create the payment (price snapshot from the DB) and return the provider redirect URL."""
    _require_buyer(user)
    kind, _, code = product.partition(":")
    with db.begin():
        credits.lock_user(db, user.id)
        if kind == "lifetime":  # serialize the last seats
            db.execute(text("SELECT pg_advisory_xact_lock(hashtext('lifetime-seats'))"))
        if kind == "package":
            package = db.execute(
                select(CreditPackage).where(CreditPackage.code == code, CreditPackage.active.is_(True))
            ).scalar_one_or_none()
            if package is None:
                raise NotFound("Pacote indisponível.", code="product_not_found")
            tool = db.get(ToolDefinition, package.tool_id)
            payment = Payment(
                id=uuid.uuid4(),
                user_id=user.id,
                purpose="package",
                package_id=package.id,
                amount_cents=package.price_cents,
                currency="BRL",
                status="created",
            )
            title = f"BaixeAI - {package.credits} fichas - {tool.package_display_name}"
        elif kind == "lifetime":
            if credits.has_lifetime(db, user.id):
                raise Conflict("Você já tem o plano vitalício.", code="already_lifetime")
            if lifetime_seats_left(db) <= 0:
                raise Conflict("As vagas do plano vitalício esgotaram.", code="lifetime_sold_out")
            plan = _plan(db, "lifetime", "lifetime")
            payment = Payment(
                id=uuid.uuid4(),
                user_id=user.id,
                purpose="lifetime",
                plan_id=plan.id,
                amount_cents=plan.price_cents,
                currency="BRL",
                status="created",
            )
            title = "BaixeAI - Plano Vitalício"
        elif kind == "plan":
            plan = _plan(db, code, "recurring")
            if credits.has_lifetime(db, user.id):
                raise Conflict("Você já tem o plano vitalício.", code="already_lifetime")
            if credits.active_recurring(db, user.id, clock.now()) is not None:
                raise Conflict("Você já tem um plano ativo. Use a troca de plano.", code="already_subscribed")
            sub = Subscription(
                id=uuid.uuid4(),
                user_id=user.id,
                plan_id=plan.id,
                kind="recurring",
                status="pending",
                renewal_mode="card_auto" if mode == "card_auto" else "manual",
            )
            db.add(sub)
            db.flush()
            if mode == "card_auto":
                notify, back = _urls(str(sub.id))
                session = provider.create_subscription(
                    subscription_id=str(sub.id),
                    reason=f"BaixeAI {plan.name}",
                    amount_cents=plan.price_cents,
                    payer_email=user.email,
                    back_url=back,
                )
                sub.provider_preapproval_id = session.provider_subscription_id
                return {"redirect_url": session.redirect_url, "subscription_id": str(sub.id)}
            payment = Payment(
                id=uuid.uuid4(),
                user_id=user.id,
                purpose="plan_cycle",
                plan_id=plan.id,
                subscription_id=sub.id,
                amount_cents=plan.price_cents,
                currency="BRL",
                status="created",
            )
            title = f"BaixeAI - Plano {plan.name} (30 dias)"
        else:
            raise NotFound("Produto indisponível.", code="product_not_found")
        db.add(payment)
        db.flush()
        notify, back = _urls(str(payment.id))
        session = provider.create_checkout(
            payment_id=str(payment.id),
            title=title,
            amount_cents=payment.amount_cents,
            payer_email=user.email,
            notification_url=notify,
            back_url=back,
        )
        payment.provider_preference_id = session.provider_reference
    return {"redirect_url": session.redirect_url, "payment_id": str(payment.id)}


def renew_manual(db: Session, provider: PaymentProvider, user: User) -> dict:
    """Pix/debit plans: pay the next cycle (it starts when the current one ends, or now if lapsed)."""
    _require_buyer(user)
    with db.begin():
        credits.lock_user(db, user.id)
        sub = db.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.kind == "recurring",
                Subscription.renewal_mode == "manual",
                Subscription.status.in_(("active", "past_due")),
            )
        ).scalar_one_or_none()
        if sub is None:
            raise NotFound("Nenhum plano com renovação manual ativo.", code="no_manual_plan")
        plan = db.get(Plan, sub.next_plan_id or sub.plan_id)
        payment = Payment(
            id=uuid.uuid4(),
            user_id=user.id,
            purpose="plan_cycle",
            plan_id=plan.id,
            subscription_id=sub.id,
            amount_cents=plan.price_cents,
            currency="BRL",
            status="created",
        )
        db.add(payment)
        db.flush()
        notify, back = _urls(str(payment.id))
        session = provider.create_checkout(
            payment_id=str(payment.id),
            title=f"BaixeAI - Renovação {plan.name}",
            amount_cents=plan.price_cents,
            payer_email=user.email,
            notification_url=notify,
            back_url=back,
        )
        payment.provider_preference_id = session.provider_reference
    return {"redirect_url": session.redirect_url, "payment_id": str(payment.id)}


# =========================================================================== provider -> our state


def _find_or_create_payment(db: Session, p: ProviderPayment) -> Payment | None:
    row = db.execute(
        select(Payment).where(Payment.provider_payment_id == p.provider_payment_id).with_for_update()
    ).scalar_one_or_none()
    if row is not None:
        return row
    try:
        ref = uuid.UUID(str(p.external_reference)) if p.external_reference else None
    except ValueError:
        ref = None
    if ref is not None:
        row = db.execute(select(Payment).where(Payment.id == ref).with_for_update()).scalar_one_or_none()
        if row is not None:
            return row
    # Recurring card charge: no payment row exists yet; attach it to the subscription.
    sub = None
    if p.subscription_id:
        sub = db.execute(
            select(Subscription).where(Subscription.provider_preapproval_id == p.subscription_id)
        ).scalar_one_or_none()
    if sub is None and ref is not None:
        sub = db.get(Subscription, ref)
    if sub is None:
        return None
    plan = db.get(Plan, sub.next_plan_id or sub.plan_id)
    new_id = uuid.uuid4()
    db.execute(
        pg_insert(Payment)
        .values(
            id=new_id,
            user_id=sub.user_id,
            purpose="plan_cycle",
            plan_id=plan.id,
            subscription_id=sub.id,
            amount_cents=plan.price_cents,
            currency="BRL",
            provider="mercadopago",
            provider_payment_id=p.provider_payment_id,
            status="pending",
            refunded_amount_cents=0,
        )
        .on_conflict_do_nothing(index_elements=["provider_payment_id"])
    )
    return db.execute(
        select(Payment).where(Payment.provider_payment_id == p.provider_payment_id).with_for_update()
    ).scalar_one()


def apply_payment(db: Session, p: ProviderPayment) -> str:
    """Apply the authoritative provider state. Idempotent. Returns what happened (for logs/tests)."""
    at = clock.now()
    after_commit: list = []
    with db.begin():
        probe = _find_or_create_payment(db, p)
        if probe is None:
            _audit(db, "payment_unknown", target=p.provider_payment_id, reference=str(p.external_reference))
            return "unknown"
        credits.lock_user(db, probe.user_id)  # lock order: user -> payment -> buckets
        payment = db.get(Payment, probe.id, with_for_update=True)
        expected_currency_ok = p.currency == "BRL"
        recurring = payment.purpose == "plan_cycle" and payment.provider_preference_id is None
        allowed_amounts = {payment.amount_cents}
        if recurring and payment.subscription_id:
            sub = db.get(Subscription, payment.subscription_id)
            allowed_amounts |= {db.get(Plan, pid).price_cents for pid in (sub.plan_id, sub.next_plan_id) if pid}
            # an admin price change does not alter existing card subscriptions: accept amounts already paid
            allowed_amounts |= set(db.execute(select(Payment.amount_cents).where(
                Payment.subscription_id == sub.id, Payment.status == "approved")).scalars())
        if p.amount_cents not in allowed_amounts or not expected_currency_ok:
            _audit(
                db,
                "payment_mismatch",
                target=str(payment.id),
                provider_amount=p.amount_cents,
                expected=sorted(allowed_amounts),
                currency=p.currency,
            )
            payment.status_detail = "amount_or_currency_mismatch"
            return "mismatch"
        if recurring:
            payment.amount_cents = p.amount_cents
        payment.provider_payment_id = p.provider_payment_id
        payment.status_detail = p.status_detail
        payment.method = p.method
        payment.updated_at = at
        if payment.status == "approved" and p.status == "pending":
            return "ignored_regression"  # out-of-order notification; never go back
        payment.status = p.status
        if p.status == "approved":
            payment.approved_at = payment.approved_at or p.approved_at or at
            if payment.fulfilled_at is None:
                after_commit += _fulfill(db, payment, at)
                payment.fulfilled_at = at
                outcome = "fulfilled"
            else:
                outcome = "already_fulfilled"
        elif p.status in ("refunded", "charged_back"):
            payment.refunded_amount_cents = max(payment.refunded_amount_cents, p.refunded_cents or payment.amount_cents)
            after_commit += _reverse(db, payment, reason=p.status)
            outcome = p.status
        else:
            outcome = p.status
    for action in after_commit:
        action()
    return outcome


def _fulfill(db: Session, payment: Payment, at: datetime) -> list:
    after: list = []
    if payment.purpose == "package":
        package = db.get(CreditPackage, payment.package_id)
        credits.grant_package(db, payment.user_id, package, at=at, payment_id=payment.id)
    elif payment.purpose == "plan_cycle":
        sub = db.get(Subscription, payment.subscription_id, with_for_update=True)
        has_cycle = (
            db.execute(select(SubscriptionCycle.id).where(SubscriptionCycle.subscription_id == sub.id)).first()
            is not None
        )
        if has_cycle and sub.status == "active" and sub.current_period_end and sub.current_period_end > at:
            start = sub.current_period_end  # early manual renewal: next cycle starts when this one ends
        else:
            start = at  # first cycle, or renewal after the end/grace (anchor = payment date, D2)
        credits.start_plan_cycle(db, sub, period_start=start, at=at, payment_id=payment.id)
        sub.cancel_at_period_end = False
    elif payment.purpose == "lifetime":
        plan = db.get(Plan, payment.plan_id)
        if not credits.has_lifetime(db, payment.user_id):
            db.add(
                Subscription(
                    user_id=payment.user_id,
                    plan_id=plan.id,
                    kind="lifetime",
                    status="active",
                    renewal_mode="one_time",
                    current_period_start=at,
                )
            )
        recurring = credits.active_recurring(db, payment.user_id, at)
        if recurring is not None:  # lifetime replaces the monthly plan at the end of the paid cycle
            recurring.cancel_at_period_end = True
            recurring.canceled_at = at
            if recurring.renewal_mode == "card_auto" and recurring.provider_preapproval_id:
                pid = recurring.provider_preapproval_id
                after.append(lambda: _safe(lambda: provider_factory().cancel_subscription(pid)))
    _audit(db, "payment_fulfilled", target=str(payment.id), purpose=payment.purpose)
    return after


def _reverse(db: Session, payment: Payment, *, reason: str, actor: str = "system") -> list:
    """Refund/chargeback: revoke what is left; never negative; shortfall is audited."""
    after: list = []
    buckets = (
        db.execute(select(CreditBucket).where(CreditBucket.source_payment_id == payment.id).with_for_update())
        .scalars()
        .all()
    )
    removed = sum(
        credits.revoke_bucket(db, b, reason=f"payment_{reason}", payment_id=payment.id, actor=actor) for b in buckets
    )
    if payment.purpose in ("plan_cycle", "lifetime"):
        sub = db.get(Subscription, payment.subscription_id, with_for_update=True) if payment.subscription_id else None
        if payment.purpose == "lifetime":
            sub = db.execute(
                select(Subscription)
                .where(
                    Subscription.user_id == payment.user_id,
                    Subscription.kind == "lifetime",
                    Subscription.status == "active",
                )
                .with_for_update()
            ).scalar_one_or_none()
        if sub is not None and sub.status not in ("refunded", "expired"):
            sub.status = "refunded"
            sub.canceled_at = clock.now()
            if sub.renewal_mode == "card_auto" and sub.provider_preapproval_id:
                pid = sub.provider_preapproval_id
                after.append(lambda: _safe(lambda: provider_factory().cancel_subscription(pid)))
    granted = sum(b.granted for b in buckets)
    if granted and removed < granted:
        _audit(db, "refund_shortfall", target=str(payment.id), granted=granted, removed=removed, reason=reason)
    _audit(db, f"payment_{reason}", target=str(payment.id), removed=removed)
    return after


def apply_subscription(db: Session, s: ProviderSubscription) -> str:
    with db.begin():
        sub = db.execute(
            select(Subscription)
            .where(Subscription.provider_preapproval_id == s.provider_subscription_id)
            .with_for_update()
        ).scalar_one_or_none()
        if sub is None:
            return "unknown"
        if s.status == "cancelled" and sub.status in ("active", "past_due") and not sub.cancel_at_period_end:
            sub.cancel_at_period_end = True  # cancelled on Mercado Pago: access until the paid cycle ends
            sub.canceled_at = clock.now()
            return "cancel_at_period_end"
        if s.status == "cancelled" and sub.status == "pending":
            sub.status = "canceled"
            return "canceled"
        return "noop"


def _safe(fn) -> None:
    try:
        fn()
    except Exception:  # noqa: BLE001 - provider side-effects are retried by reconciliation/admin
        log.exception("provider side-effect failed")


def provider_factory() -> PaymentProvider:
    from app.payments import get_provider

    return get_provider()


# =========================================================================== user actions


def cancel(db: Session, provider: PaymentProvider, user: User) -> None:
    with db.begin():
        credits.lock_user(db, user.id)
        sub = credits.active_recurring(db, user.id, clock.now())
        if sub is None:
            raise NotFound("Nenhum plano ativo.", code="no_active_plan")
        sub.cancel_at_period_end = True
        sub.canceled_at = clock.now()
        pid = sub.provider_preapproval_id if sub.renewal_mode == "card_auto" else None
    if pid:
        provider.cancel_subscription(pid)  # no further card charges; access until period end


def change_plan(db: Session, provider: PaymentProvider, user: User, plan_code: str) -> None:
    """D5: takes effect at the next cycle, no pro-rata; leftover plan credits carry over."""
    with db.begin():
        credits.lock_user(db, user.id)
        sub = credits.active_recurring(db, user.id, clock.now())
        if sub is None:
            raise NotFound("Nenhum plano ativo.", code="no_active_plan")
        plan = _plan(db, plan_code, "recurring")
        sub.next_plan_id = None if plan.id == sub.plan_id else plan.id
        pid, amount = (sub.provider_preapproval_id, plan.price_cents) if sub.renewal_mode == "card_auto" else (None, 0)
    if pid:
        provider.update_subscription_amount(pid, amount)  # next card charge uses the new price


# =========================================================================== admin refund (D5)


def admin_refund(db: Session, provider: PaymentProvider, payment_id: uuid.UUID, admin: User) -> dict:
    """Within 7 days of approval; amount proportional to UNUSED credits (lifetime: full amount within
    7 days — pending legal review). Executes on the provider, then revokes immediately (the later
    webhook is idempotent)."""
    at = clock.now()
    with db.begin():
        payment = db.get(Payment, payment_id, with_for_update=True)
        if payment is None or payment.status != "approved" or not payment.provider_payment_id:
            raise NotFound("Pagamento aprovado não encontrado.", code="payment_not_found")
        window = timedelta(days=int(get_setting(db, "refund_window_days")))
        if payment.approved_at is None or at - payment.approved_at > window:
            raise Conflict("Fora do prazo de reembolso (7 dias).", code="refund_window_closed")
        buckets = db.execute(select(CreditBucket).where(CreditBucket.source_payment_id == payment.id)).scalars().all()
        if payment.purpose == "lifetime":
            amount = payment.amount_cents
        else:
            granted = sum(b.granted for b in buckets) or 1
            unused = sum(b.available for b in buckets)
            amount = payment.amount_cents * unused // granted
        if amount <= 0:
            raise Conflict("Todas as fichas deste pagamento já foram usadas.", code="nothing_to_refund")
    provider.refund(payment.provider_payment_id, amount, idempotency_key=f"refund-{payment.id}")
    with db.begin():
        credits.lock_user(db, payment.user_id)
        payment = db.get(Payment, payment_id, with_for_update=True)
        payment.refunded_amount_cents = amount
        payment.status = "refunded"
        after = _reverse(db, payment, reason="refunded", actor=str(admin.id))
        _audit(db, "admin_refund", actor=str(admin.id), target=str(payment.id), amount_cents=amount)
    for action in after:
        action()
    return {"refunded_cents": amount}


# =========================================================================== maintenance


def subscription_maintenance(db_factory, provider: PaymentProvider | None = None, at: datetime | None = None) -> dict:
    """Grace period, expirations and renewal reminders. Safe to run repeatedly."""
    at = at or clock.now()
    counts = {"past_due": 0, "expired": 0, "reminded": 0}
    with db_factory() as db:
        grace = timedelta(days=int(get_setting(db, "card_grace_days")))
        remind = timedelta(days=int(get_setting(db, "renewal_reminder_days")))
        rows = (
            db.execute(
                select(Subscription.id).where(
                    Subscription.kind == "recurring", Subscription.status.in_(("active", "past_due"))
                )
            )
            .scalars()
            .all()
        )
    to_cancel: list[str] = []
    for sub_id in rows:
        with db_factory() as db, db.begin():
            sub = db.get(Subscription, sub_id, with_for_update=True)
            end = sub.current_period_end
            if end is None:
                continue
            if sub.status == "active" and end <= at:
                if sub.cancel_at_period_end or sub.renewal_mode != "card_auto":
                    sub.status = "expired"
                    counts["expired"] += 1
                else:
                    sub.status = "past_due"  # card charge did not arrive: grace period (no new credits)
                    counts["past_due"] += 1
            elif sub.status == "past_due" and end + grace <= at:
                sub.status = "expired"
                counts["expired"] += 1
                if sub.provider_preapproval_id:
                    to_cancel.append(sub.provider_preapproval_id)
            elif (
                sub.status == "active"
                and sub.renewal_mode == "manual"
                and not sub.cancel_at_period_end
                and end - remind <= at < end
                and _remind_once(str(sub.id), end)
            ):
                user = db.get(User, sub.user_id)
                from app.services import email

                email.send(
                    user.email,
                    "Seu plano BaixeAI vence em breve",
                    f"Seu plano vence em {end.astimezone(clock.local_tz()):%d/%m/%Y}. "
                    f"Renove pelo painel: {get_settings().app_base_url}/painel",
                )
                counts["reminded"] += 1
    for pid in to_cancel:
        if provider is not None:
            _safe(lambda pid=pid: provider.cancel_subscription(pid))
    return counts


def _remind_once(sub_id: str, end: datetime) -> bool:
    from app.security.rate_limit import get_redis

    return bool(get_redis().set(f"renewal-reminder:{sub_id}:{end.date().isoformat()}", 1, nx=True, ex=86400 * 10))


def reconcile(db_factory, provider: PaymentProvider, at: datetime | None = None) -> dict:
    """Pending/created payments older than 5 min are re-checked on the provider (covers lost webhooks)."""
    at = at or clock.now()
    with db_factory() as db:
        rows = db.execute(
            select(Payment.id, Payment.provider_payment_id).where(
                Payment.status.in_(("created", "pending")),
                Payment.created_at < at - timedelta(minutes=5),
                Payment.created_at > at - timedelta(days=3),
            )
        ).all()
    applied = 0
    for payment_id, provider_payment_id in rows:
        try:
            found = (
                [provider.get_payment(provider_payment_id)]
                if provider_payment_id
                else provider.find_payments(str(payment_id))
            )
        except Exception:  # noqa: BLE001
            log.exception("reconcile fetch failed")
            continue
        for p in found:
            with db_factory() as db:
                apply_payment(db, p)
                applied += 1
    with db_factory() as db:
        divergent = (
            db.execute(select(Payment.id).where(Payment.status == "approved", Payment.fulfilled_at.is_(None)))
            .scalars()
            .all()
        )
    if divergent:
        log.error("approved payments without fulfillment", extra={"payments": [str(d) for d in divergent]})
    return {"checked": len(rows), "applied": applied, "approved_not_fulfilled": [str(d) for d in divergent]}
