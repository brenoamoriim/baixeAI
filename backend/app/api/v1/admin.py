"""Admin API (RBAC: every route requires role=admin). Sensitive changes require re-typing the password."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.db import get_db
from app.models import (
    AuditEvent,
    CreditCostRule,
    CreditPackage,
    FeatureFlag,
    Payment,
    Plan,
    Subscription,
    SystemSetting,
    ToolCapability,
    ToolDefinition,
    User,
)
from app.payments import get_provider
from app.services import admin as service
from app.services import payments as payment_service

router = APIRouter(prefix="/admin", tags=["admin"])


class Reauth(BaseModel):
    confirm_password: str | None = Field(default=None, max_length=256)


class ToolPatch(Reauth):
    enabled: bool | None = None
    credit_cost: int | None = None


class CapabilityPatch(Reauth):
    status: str = Field(pattern=r"^(available|planned|unsupported)$")


class CostRulePatch(Reauth):
    cost: int | None = None
    active: bool | None = None


class PlanPatch(Reauth):
    price_cents: int | None = None
    active: bool | None = None
    credits_per_cycle: int | None = None


class PackagePatch(Reauth):
    price_cents: int | None = None
    active: bool | None = None


class SettingPatch(BaseModel):
    value: Any


class FlagPatch(BaseModel):
    enabled: bool


class SuspendBody(Reauth):
    suspended: bool


@router.get("/overview")
def overview(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    return service.overview(db)


# ---- tools / capabilities / cost rules


@router.get("/tools")
def tools(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(ToolDefinition).order_by(ToolDefinition.sort_order)).scalars()
    return {
        "tools": [
            {
                "id": t.id,
                "name": t.display_name,
                "enabled": t.enabled,
                "credit_cost": t.credit_cost,
                "dev_only": t.dev_only,
            }
            for t in rows
        ]
    }


@router.patch("/tools/{tool_id}")
def patch_tool(tool_id: str, body: ToolPatch, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    service.require_reauth(admin, body.confirm_password)
    service.update_tool(db, admin, tool_id, enabled=body.enabled, credit_cost=body.credit_cost)
    return {"message": "Ferramenta atualizada."}


@router.get("/capabilities")
def capabilities(
    tool_id: str = Query(pattern=r"^[a-z_]{1,40}$"), _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    rows = db.execute(
        select(ToolCapability)
        .where(ToolCapability.tool_id == tool_id)
        .order_by(ToolCapability.category, ToolCapability.input_format, ToolCapability.output_format)
    ).scalars()
    return {
        "capabilities": [
            {
                "id": str(c.id),
                "category": c.category,
                "input": c.input_format,
                "output": c.output_format,
                "status": c.status,
                "engine": c.engine,
                "note": c.notes,
            }
            for c in rows
        ]
    }


@router.patch("/capabilities/{capability_id}")
def patch_capability(
    capability_id: uuid.UUID, body: CapabilityPatch, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    service.require_reauth(admin, body.confirm_password)
    service.update_capability(db, admin, capability_id, body.status)
    return {"message": "Combinação atualizada."}


@router.get("/cost-rules")
def cost_rules(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(CreditCostRule).order_by(CreditCostRule.tool_id)).scalars()
    return {
        "rules": [
            {
                "id": str(r.id),
                "tool_id": r.tool_id,
                "category": r.category,
                "min_duration_seconds": r.min_duration_seconds,
                "cost": r.cost,
                "active": r.active,
            }
            for r in rows
        ]
    }


@router.patch("/cost-rules/{rule_id}")
def patch_cost_rule(
    rule_id: uuid.UUID, body: CostRulePatch, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    service.require_reauth(admin, body.confirm_password)
    service.update_cost_rule(db, admin, rule_id, cost=body.cost, active=body.active)
    return {"message": "Regra atualizada."}


# ---- catalog


@router.get("/catalog")
def catalog(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    plans = db.execute(select(Plan).order_by(Plan.price_cents)).scalars()
    packs = db.execute(select(CreditPackage).order_by(CreditPackage.code)).scalars()
    return {
        "plans": [
            {
                "code": p.code,
                "name": p.name,
                "kind": p.kind,
                "price_cents": p.price_cents,
                "credits_per_cycle": p.credits_per_cycle,
                "active": p.active,
            }
            for p in plans
        ],
        "packages": [
            {
                "code": p.code,
                "tool_id": p.tool_id,
                "credits": p.credits,
                "price_cents": p.price_cents,
                "validity_days": p.validity_days,
                "active": p.active,
            }
            for p in packs
        ],
    }


@router.patch("/plans/{code}")
def patch_plan(code: str, body: PlanPatch, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    service.require_reauth(admin, body.confirm_password)
    service.update_plan(
        db, admin, code, price_cents=body.price_cents, active=body.active, credits_per_cycle=body.credits_per_cycle
    )
    return {"message": "Plano atualizado. Assinaturas no cartão já existentes mantêm o valor contratado."}


@router.patch("/packages/{code}")
def patch_package(code: str, body: PackagePatch, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    service.require_reauth(admin, body.confirm_password)
    service.update_package(db, admin, code, price_cents=body.price_cents, active=body.active)
    return {"message": "Pacote atualizado."}


# ---- settings / flags


@router.get("/settings")
def list_settings(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(SystemSetting).order_by(SystemSetting.key)).scalars()
    return {
        "settings": [
            {
                "key": r.key,
                "value": r.value,
                "description": r.description,
                "editable": r.key in service.SETTING_VALIDATORS,
            }
            for r in rows
        ]
    }


@router.patch("/settings/{key}")
def patch_setting(key: str, body: SettingPatch, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    service.update_setting(db, admin, key, body.value)
    return {"message": "Configuração salva."}


@router.get("/flags")
def flags(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(FeatureFlag).order_by(FeatureFlag.key)).scalars()
    return {"flags": [{"key": f.key, "enabled": f.enabled, "description": f.description} for f in rows]}


@router.patch("/flags/{key}")
def patch_flag(key: str, body: FlagPatch, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    service.set_flag(db, admin, key, body.enabled)
    return {"message": "Flag atualizada."}


# ---- payments / subscriptions / audit / users


@router.get("/payments")
def payments(
    status: str | None = Query(default=None, pattern=r"^[a-z_]{1,20}$"),
    limit: int = Query(50, le=200),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    stmt = (
        select(Payment, User.email)
        .join(User, User.id == Payment.user_id)
        .order_by(Payment.created_at.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(Payment.status == status)
    return {
        "payments": [
            {
                "id": str(p.id),
                "email": email,
                "purpose": p.purpose,
                "amount_cents": p.amount_cents,
                "status": p.status,
                "method": p.method,
                "created_at": p.created_at.isoformat(),
                "approved_at": p.approved_at.isoformat() if p.approved_at else None,
                "fulfilled": p.fulfilled_at is not None,
                "refunded_amount_cents": p.refunded_amount_cents,
            }
            for p, email in db.execute(stmt)
        ]
    }


@router.post("/payments/{payment_id}/refund")
def refund(payment_id: uuid.UUID, body: Reauth, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    service.require_reauth(admin, body.confirm_password)
    return payment_service.admin_refund(db, get_provider(), payment_id, admin)


@router.post("/payments/reconcile")
def reconcile(_: User = Depends(require_admin)) -> dict:
    from app.core.db import SessionLocal

    return payment_service.reconcile(SessionLocal, get_provider())


@router.get("/subscriptions")
def subscriptions(
    status: str | None = Query(default=None, pattern=r"^[a-z_]{1,20}$"),
    limit: int = Query(50, le=200),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    stmt = (
        select(Subscription, User.email, Plan.code)
        .join(User, User.id == Subscription.user_id)
        .join(Plan, Plan.id == Subscription.plan_id)
        .order_by(Subscription.created_at.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(Subscription.status == status)
    return {
        "subscriptions": [
            {
                "id": str(s.id),
                "email": email,
                "plan": code,
                "kind": s.kind,
                "status": s.status,
                "renewal_mode": s.renewal_mode,
                "cancel_at_period_end": s.cancel_at_period_end,
                "period_end": s.current_period_end.isoformat() if s.current_period_end else None,
            }
            for s, email, code in db.execute(stmt)
        ]
    }


@router.get("/audit")
def audit_log(
    action: str | None = Query(default=None, pattern=r"^[a-z_]{1,80}$"),
    limit: int = Query(100, le=500),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    stmt = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    return {
        "events": [
            {
                "id": e.id,
                "actor_type": e.actor_type,
                "actor_id": e.actor_id,
                "action": e.action,
                "target_type": e.target_type,
                "target_id": e.target_id,
                "metadata": e.metadata_,
                "created_at": e.created_at.isoformat(),
            }
            for e in db.execute(stmt).scalars()
        ]
    }


@router.get("/users")
def users(q: str = Query(default="", max_length=120), _: User = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(User).order_by(User.created_at.desc()).limit(50)
    if q:
        stmt = stmt.where(or_(User.email.ilike(f"%{q.replace('%', '').replace('_', '')}%")))
    return {
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "role": u.role,
                "status": u.status,
                "email_verified": u.email_verified_at is not None,
                "created_at": u.created_at.isoformat(),
            }
            for u in db.execute(stmt).scalars()
        ]
    }


@router.post("/users/{user_id}/suspend")
def suspend(user_id: uuid.UUID, body: SuspendBody, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    service.require_reauth(admin, body.confirm_password)
    service.set_suspended(db, admin, user_id, body.suspended)
    return {"message": "Usuário suspenso." if body.suspended else "Usuário reativado."}
