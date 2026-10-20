"""Admin operations (RBAC enforced in the API layer). Every change is audited. Sensitive changes
(prices, availability, user suspension, refunds) require the admin to re-type the password.

Availability rule kept even for admins: a capability can only be set to `available` if it passed
the real verification (verified.json); admins can always take one OUT of availability.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.models import (
    AuditEvent,
    CreditCostRule,
    CreditPackage,
    FeatureFlag,
    Payment,
    Plan,
    ProcessingJob,
    Subscription,
    SystemSetting,
    ToolCapability,
    ToolDefinition,
    User,
    UserSession,
)
from app.security.crypto import verify_password
from app.security.rate_limit import hit
from app.services.settings import DEFAULTS


def require_reauth(admin: User, password: str | None) -> None:
    hit(f"admin:reauth:{admin.id}", limit=10, window_seconds=600)
    if not password or not verify_password(admin.password_hash, password):
        raise Forbidden("Confirme sua senha para esta ação.", code="reauth_failed")


def audit(db: Session, admin: User, action: str, target_type: str, target_id: str, **meta) -> None:
    db.add(
        AuditEvent(
            actor_type="admin",
            actor_id=str(admin.id),
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_=meta,
        )
    )


# --------------------------------------------------------------------------- overview


def overview(db: Session) -> dict:
    since = clock.now() - timedelta(hours=24)
    month = clock.now() - timedelta(days=30)
    jobs = db.execute(
        select(ProcessingJob.tool_id, ProcessingJob.status, func.count())
        .where(ProcessingJob.created_at >= since)
        .group_by(ProcessingJob.tool_id, ProcessingJob.status)
    ).all()
    failures = db.execute(
        select(ProcessingJob.tool_id, ProcessingJob.error_class, ProcessingJob.error_code, func.count())
        .where(ProcessingJob.created_at >= since, ProcessingJob.status == "failed")
        .group_by(ProcessingJob.tool_id, ProcessingJob.error_class, ProcessingJob.error_code)
        .order_by(func.count().desc())
        .limit(20)
    ).all()
    revenue = db.execute(
        select(func.coalesce(func.sum(Payment.amount_cents - Payment.refunded_amount_cents), 0)).where(
            Payment.status.in_(("approved", "refunded")), Payment.approved_at >= month
        )
    ).scalar_one()
    return {
        "users": db.execute(select(func.count()).select_from(User).where(User.status != "deleted")).scalar_one(),
        "active_subscriptions": db.execute(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.kind == "recurring", Subscription.status == "active")
        ).scalar_one(),
        "lifetime": db.execute(
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.kind == "lifetime", Subscription.status == "active")
        ).scalar_one(),
        "jobs_24h": [{"tool_id": t, "status": s, "count": c} for t, s, c in jobs],
        "failures_24h": [{"tool_id": t, "error_class": k, "error_code": e, "count": c} for t, k, e, c in failures],
        "revenue_30d_cents": int(revenue),
        "pending_payments": db.execute(
            select(func.count()).select_from(Payment).where(Payment.status == "pending")
        ).scalar_one(),
        "health": _health(db),
    }


def _health(db: Session) -> dict | None:
    from app.services import monitoring

    try:
        return monitoring.snapshot(db)
    except Exception:  # noqa: BLE001 - the overview must load even if Redis/disk checks fail
        return None


# --------------------------------------------------------------------------- tools & capabilities


def _verified_keys() -> dict[str, set[str]]:
    from app.tools.ai import verify as ai_verify
    from app.tools.converter import matrix
    from app.tools.downloader import verify as dl_verify

    ai = ai_verify.verified_keys()
    return {
        "converter": matrix.verified_keys(),
        "background_remover": {k.split(":", 1)[1] for k in ai if k.startswith("background_remover:")},
        "object_remover": {k.split(":", 1)[1] for k in ai if k.startswith("object_remover:")},
        "video_downloader": dl_verify.verified_keys(),
        "echo": {"text->txt"},
    }


def update_tool(db: Session, admin: User, tool_id: str, *, enabled: bool | None, credit_cost: int | None) -> None:
    with db.begin():
        tool = db.get(ToolDefinition, tool_id, with_for_update=True)
        if tool is None:
            raise NotFound("Ferramenta não encontrada.")
        if credit_cost is not None:
            if not 1 <= credit_cost <= 100:
                raise AppError("Custo deve ser entre 1 e 100 fichas.", code="invalid_value")
            audit(db, admin, "tool_cost_changed", "tool", tool_id, old=tool.credit_cost, new=credit_cost)
            tool.credit_cost = credit_cost
        if enabled is not None:
            audit(db, admin, "tool_enabled_changed", "tool", tool_id, old=tool.enabled, new=enabled)
            tool.enabled = enabled


def update_capability(db: Session, admin: User, capability_id, status: str) -> None:
    with db.begin():
        cap = db.get(ToolCapability, capability_id, with_for_update=True)
        if cap is None:
            raise NotFound("Combinação não encontrada.")
        if status == "available":
            key = f"{cap.input_format}->{cap.output_format}"
            if key not in _verified_keys().get(cap.tool_id, set()):
                raise Conflict(
                    "Só é possível disponibilizar combinações aprovadas na verificação real.", code="not_verified"
                )
        elif status not in ("planned", "unsupported"):
            raise AppError("Status inválido.", code="invalid_value")
        audit(db, admin, "capability_status_changed", "capability", str(cap.id), old=cap.status, new=status)
        cap.status = status


def update_cost_rule(db: Session, admin: User, rule_id, *, cost: int | None, active: bool | None) -> None:
    with db.begin():
        rule = db.get(CreditCostRule, rule_id, with_for_update=True)
        if rule is None:
            raise NotFound("Regra não encontrada.")
        if cost is not None:
            if not 1 <= cost <= 100:
                raise AppError("Custo deve ser entre 1 e 100 fichas.", code="invalid_value")
            audit(db, admin, "cost_rule_changed", "cost_rule", str(rule.id), old=rule.cost, new=cost)
            rule.cost = cost
        if active is not None:
            audit(db, admin, "cost_rule_active_changed", "cost_rule", str(rule.id), old=rule.active, new=active)
            rule.active = active


# --------------------------------------------------------------------------- catalog


def update_plan(
    db: Session, admin: User, code: str, *, price_cents: int | None, active: bool | None, credits_per_cycle: int | None
) -> None:
    with db.begin():
        plan = db.execute(select(Plan).where(Plan.code == code).with_for_update()).scalar_one_or_none()
        if plan is None or plan.kind == "free":
            raise NotFound("Plano não encontrado.")
        if price_cents is not None:
            if not 100 <= price_cents <= 1_000_000:
                raise AppError("Preço fora do intervalo permitido.", code="invalid_value")
            audit(db, admin, "plan_price_changed", "plan", code, old=plan.price_cents, new=price_cents)
            plan.price_cents = price_cents
        if credits_per_cycle is not None and plan.kind == "recurring":
            if not 1 <= credits_per_cycle <= 100_000:
                raise AppError("Fichas por ciclo fora do intervalo.", code="invalid_value")
            audit(db, admin, "plan_credits_changed", "plan", code, old=plan.credits_per_cycle, new=credits_per_cycle)
            plan.credits_per_cycle = credits_per_cycle
        if active is not None:
            audit(db, admin, "plan_active_changed", "plan", code, old=plan.active, new=active)
            plan.active = active


def update_package(db: Session, admin: User, code: str, *, price_cents: int | None, active: bool | None) -> None:
    with db.begin():
        pack = db.execute(
            select(CreditPackage).where(CreditPackage.code == code).with_for_update()
        ).scalar_one_or_none()
        if pack is None:
            raise NotFound("Pacote não encontrado.")
        if price_cents is not None:
            if not 100 <= price_cents <= 1_000_000:
                raise AppError("Preço fora do intervalo permitido.", code="invalid_value")
            audit(db, admin, "package_price_changed", "package", code, old=pack.price_cents, new=price_cents)
            pack.price_cents = price_cents
        if active is not None:
            audit(db, admin, "package_active_changed", "package", code, old=pack.active, new=active)
            pack.active = active


# --------------------------------------------------------------------------- settings & flags


def _int(lo: int, hi: int):
    def check(v: Any) -> Any:
        if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
            raise AppError(f"Valor deve ser inteiro entre {lo} e {hi}.", code="invalid_value")
        return v

    return check


def _limits(v: Any) -> Any:
    if not isinstance(v, dict) or set(v) != {"image", "document", "audio", "video"}:
        raise AppError("Informe os 4 limites (image, document, audio, video).", code="invalid_value")
    for size in v.values():
        _int(1024, 95 * 1024 * 1024)(size)  # 95 MB = Cloudflare Free body limit (D10)
    return v


def _optional_str(max_len: int):
    def check(v: Any) -> Any:
        if v is not None and (not isinstance(v, str) or len(v) > max_len):
            raise AppError("Texto inválido.", code="invalid_value")
        return v

    return check


def _slots(v: Any) -> Any:
    if not isinstance(v, dict) or not all(
        isinstance(k, str) and isinstance(s, str) and s.isdigit() for k, s in v.items()
    ):
        raise AppError("Slots devem ser {nome: id numérico}.", code="invalid_value")
    return v


SETTING_VALIDATORS = {
    "daily_free_credits": _int(0, 100),
    "guest_credits": _int(0, 5),
    "guest_max_per_ip_per_day": _int(0, 100),
    "package_validity_days": _int(1, 365),
    "compensation_validity_hours": _int(1, 168),
    "lifetime_max_concurrent_jobs": _int(1, 10),
    "lifetime_daily_cap": _int(1, 1000),
    "lifetime_max_seats": _int(0, 100000),
    "max_pending_jobs_per_user": _int(1, 50),
    "job_stuck_after_seconds": _int(300, 86400),
    "limits_bytes": _limits,
    "video_max_seconds": _int(10, 3600),
    "audio_max_seconds": _int(10, 14400),
    "image_max_pixels": _int(1_000_000, 100_000_000),
    "doc_max_pages": _int(1, 2000),
    "download_max_bytes": _int(1024 * 1024, 2 * 1024**3),
    "download_max_seconds": _int(10, 7200),
    "card_grace_days": _int(0, 30),
    "refund_window_days": _int(0, 30),
    "renewal_reminder_days": _int(0, 14),
    "adsense_client_id": _optional_str(40),
    "adsense_slots": _slots,
    "support_email": _optional_str(120),
}


def update_setting(db: Session, admin: User, key: str, value: Any) -> None:
    validator = SETTING_VALIDATORS.get(key)
    if validator is None:
        raise AppError("Configuração não editável.", code="not_editable")
    value = validator(value)
    if key == "adsense_client_id" and value and not value.startswith("ca-pub-"):
        raise AppError("O ID do AdSense começa com ca-pub-.", code="invalid_value")
    with db.begin():
        row = db.get(SystemSetting, key, with_for_update=True)
        old = row.value if row else DEFAULTS.get(key, (None, ""))[0]
        if row is None:
            db.add(
                SystemSetting(key=key, value=value, description=DEFAULTS.get(key, (None, ""))[1], updated_by=admin.id)
            )
        else:
            row.value = value
            row.updated_by = admin.id
            row.updated_at = clock.now()
        audit(db, admin, "setting_changed", "setting", key, old=old, new=value)


def set_flag(db: Session, admin: User, key: str, enabled: bool) -> None:
    with db.begin():
        flag = db.get(FeatureFlag, key, with_for_update=True)
        if flag is None:
            raise NotFound("Flag não encontrada.")
        audit(db, admin, "flag_changed", "flag", key, old=flag.enabled, new=enabled)
        flag.enabled = enabled
        flag.updated_by = admin.id
        flag.updated_at = clock.now()


# --------------------------------------------------------------------------- users


def set_suspended(db: Session, admin: User, user_id, suspended: bool) -> None:
    if user_id == admin.id:
        raise Conflict("Você não pode suspender a própria conta.", code="self_action")
    with db.begin():
        user = db.get(User, user_id, with_for_update=True)
        if user is None or user.status == "deleted":
            raise NotFound("Usuário não encontrado.")
        new = "suspended" if suspended else "active"
        audit(db, admin, "user_status_changed", "user", str(user.id), old=user.status, new=new)
        user.status = new
        if suspended:
            db.execute(
                update(UserSession)
                .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
                .values(revoked_at=clock.now())
            )
