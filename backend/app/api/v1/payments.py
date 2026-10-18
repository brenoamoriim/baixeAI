import json
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.deps import current_user, require_admin
from app.core import clock
from app.core.db import get_db
from app.core.errors import NotFound
from app.models import Payment, PaymentEvent, Plan, Subscription, User
from app.payments import get_provider
from app.payments.provider import InvalidWebhook
from app.security.rate_limit import hit
from app.services import credits
from app.services import payments as service

router = APIRouter(tags=["payments"])
webhook_router = APIRouter(tags=["webhooks"])
MAX_WEBHOOK_BODY = 64 * 1024


class CheckoutBody(BaseModel):
    # Only WHICH product. Any price/amount sent by the client is ignored (extra fields dropped).
    product: str = Field(pattern=r"^(package:[a-z0-9_]{1,40}|plan:(pro|premium)|lifetime)$")
    mode: str = Field(default="manual", pattern=r"^(manual|card_auto)$")


class ChangePlanBody(BaseModel):
    plan: str = Field(pattern=r"^(pro|premium)$")


def _payment_view(p: Payment) -> dict:
    return {
        "id": str(p.id),
        "purpose": p.purpose,
        "amount_cents": p.amount_cents,
        "currency": p.currency,
        "status": p.status,
        "method": p.method,
        "created_at": p.created_at.isoformat(),
        "approved_at": p.approved_at.isoformat() if p.approved_at else None,
        "fulfilled": p.fulfilled_at is not None,
        "refunded_amount_cents": p.refunded_amount_cents,
    }


@router.get("/catalog")
def catalog(db: Session = Depends(get_db)) -> dict:
    return service.catalog(db)


@router.post("/checkout")
def checkout(body: CheckoutBody, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    hit(f"checkout:u:{user.id}", limit=10, window_seconds=600)
    return service.start_checkout(db, get_provider(), user, body.product, body.mode)


@router.get("/payments")
def my_payments(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(
        select(Payment)
        .where(Payment.user_id == user.id, Payment.status != "created")
        .order_by(Payment.created_at.desc())
        .limit(50)
    ).scalars()
    return {"payments": [_payment_view(p) for p in rows]}


@router.get("/payments/{payment_id}")
def payment_status(payment_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Used by the return page. Only shows what the webhook/reconciliation recorded; never grants."""
    p = db.get(Payment, payment_id)
    if p is None or p.user_id != user.id:
        sub = db.get(Subscription, payment_id)  # card subscriptions return with the subscription id
        if sub is None or sub.user_id != user.id:
            raise NotFound("Pagamento não encontrado.")
        return {"id": str(sub.id), "purpose": "subscription", "status": sub.status, "fulfilled": sub.status == "active"}
    return _payment_view(p)


@router.get("/subscription")
def my_subscription(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    sub = db.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.kind == "recurring",
            Subscription.status.in_(("active", "past_due")),
        )
    ).scalar_one_or_none()
    lifetime = credits.has_lifetime(db, user.id)
    if sub is None:
        return {"subscription": None, "lifetime": lifetime}
    plan = db.get(Plan, sub.plan_id)
    nxt = db.get(Plan, sub.next_plan_id) if sub.next_plan_id else None
    return {
        "lifetime": lifetime,
        "subscription": {
            "plan": plan.code,
            "plan_name": plan.name,
            "status": sub.status,
            "renewal_mode": sub.renewal_mode,
            "period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "next_plan": nxt.code if nxt else None,
        },
    }


@router.post("/subscription/cancel")
def cancel(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    service.cancel(db, get_provider(), user)
    return {"message": "Assinatura cancelada. Você mantém o plano até o fim do ciclo pago."}


@router.post("/subscription/change")
def change(body: ChangePlanBody, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    service.change_plan(db, get_provider(), user, body.plan)
    return {"message": "Troca agendada para o próximo ciclo. As fichas que sobrarem serão somadas ao novo plano."}


@router.post("/subscription/renew")
def renew(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    hit(f"checkout:u:{user.id}", limit=10, window_seconds=600)
    return service.renew_manual(db, get_provider(), user)


# ------------------------------------------------------------------ admin


@router.post("/admin/payments/{payment_id}/refund")
def admin_refund(payment_id: uuid.UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    return service.admin_refund(db, get_provider(), payment_id, admin)


@router.post("/admin/payments/reconcile")
def admin_reconcile(_: User = Depends(require_admin)) -> dict:
    from app.core.db import SessionLocal

    return service.reconcile(SessionLocal, get_provider())


# ------------------------------------------------------------------ webhook


@webhook_router.post("/api/webhooks/mercadopago")
async def mercadopago_webhook(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    """Authenticated by HMAC signature (no CSRF). Fast: verify, dedupe, enqueue, 200."""
    raw = await request.body()
    if len(raw) > MAX_WEBHOOK_BODY:
        return JSONResponse(status_code=413, content={"error": "too_large"})
    try:
        body = json.loads(raw or b"{}")
        if not isinstance(body, dict):
            raise ValueError
    except ValueError:
        body = {}
    try:
        event = get_provider().parse_webhook(dict(request.headers), dict(request.query_params), body)
    except InvalidWebhook as exc:
        with db.begin():
            db.add(
                PaymentEvent(
                    provider="mercadopago",
                    dedup_key=f"invalid:{uuid.uuid4()}",
                    signature_valid=False,
                    topic=str(body.get("type"))[:60] if body.get("type") else None,
                    last_error=exc.reason,
                    payload={"keys": sorted(body)[:20]},
                )
            )
        return JSONResponse(status_code=401, content={"error": "invalid_signature"})
    with db.begin():
        inserted = db.execute(
            pg_insert(PaymentEvent)
            .values(
                provider="mercadopago",
                dedup_key=event.dedup_key,
                topic=event.topic[:60],
                action=(event.action or "")[:60],
                resource_id=event.resource_id[:80],
                signature_valid=True,
                attempts=0,
                payload=event.payload,
                received_at=clock.now(),
            )
            .on_conflict_do_nothing(index_elements=["dedup_key"])
            .returning(PaymentEvent.id)
        ).scalar_one_or_none()
    if inserted is not None:
        from app.workers.tasks import process_payment_event

        process_payment_event.apply_async(args=[inserted], queue="default")
    return JSONResponse(status_code=200, content={"received": True, "duplicate": inserted is None})
