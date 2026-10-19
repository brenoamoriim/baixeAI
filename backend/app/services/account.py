"""User account self-service: password change, data export and account deletion (LGPD).

Deletion anonymizes personal data and keeps financial/ledger records (legal and accounting
obligations); files are deleted. The legal basis and retention periods need a lawyer's review.
"""

import contextlib
import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import AppError, Forbidden
from app.models import (
    AuditEvent,
    CreditBucket,
    CreditLedger,
    Payment,
    ProcessingJob,
    Subscription,
    TermsAcceptance,
    Upload,
    UrlInspection,
    User,
    UserSession,
)
from app.security.crypto import hash_password, verify_password
from app.services import credits
from app.services.auth import _validate_password
from app.storage.base import get_storage


def _iso(value):
    return value.isoformat() if isinstance(value, datetime) else value


def change_password(db: Session, user: User, current: str, new: str, keep_session_hash: str | None) -> None:
    _validate_password(new)
    with db.begin():
        row = db.get(User, user.id, with_for_update=True)
        if not verify_password(row.password_hash, current):
            raise Forbidden("Senha atual incorreta.", code="wrong_password")
        row.password_hash = hash_password(new)
        stmt = update(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        if keep_session_hash:
            stmt = stmt.where(UserSession.token_hash != keep_session_hash)  # stay signed in here only
        db.execute(stmt.values(revoked_at=clock.now()))
        db.add(
            AuditEvent(
                actor_type="user",
                actor_id=str(user.id),
                action="password_changed",
                target_type="user",
                target_id=str(user.id),
                metadata_={},
            )
        )


def export_data(db: Session, user: User) -> dict:
    """Everything we hold about the user, in a portable JSON (LGPD art. 18)."""

    def rows(model, *where, cols):
        return [{c: _iso(getattr(r, c)) for c in cols} for r in db.execute(select(model).where(*where)).scalars()]

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "account": {
            "email": user.email,
            "created_at": _iso(user.created_at),
            "email_verified_at": _iso(user.email_verified_at),
            "role": user.role,
        },
        "sessions": rows(
            UserSession,
            UserSession.user_id == user.id,
            cols=("created_at", "last_seen_at", "expires_at", "revoked_at", "user_agent"),
        ),
        "credit_buckets": rows(
            CreditBucket,
            CreditBucket.user_id == user.id,
            cols=("kind", "tool_id", "granted", "available", "reserved", "valid_from", "expires_at", "status"),
        ),
        "credit_ledger": rows(
            CreditLedger,
            CreditLedger.user_id == user.id,
            cols=("entry_type", "delta_available", "delta_reserved", "reason", "created_at"),
        ),
        "jobs": rows(
            ProcessingJob,
            ProcessingJob.user_id == user.id,
            cols=("tool_id", "status", "credit_cost", "charged_from", "error_code", "created_at", "finished_at"),
        ),
        "payments": rows(
            Payment,
            Payment.user_id == user.id,
            cols=(
                "purpose",
                "amount_cents",
                "currency",
                "status",
                "method",
                "created_at",
                "approved_at",
                "refunded_amount_cents",
            ),
        ),
        "subscriptions": rows(
            Subscription,
            Subscription.user_id == user.id,
            cols=(
                "kind",
                "status",
                "renewal_mode",
                "current_period_start",
                "current_period_end",
                "cancel_at_period_end",
                "created_at",
            ),
        ),
        "terms_acceptances": rows(
            TermsAcceptance, TermsAcceptance.user_id == user.id, cols=("document", "version", "accepted_at")
        ),
        "note": "IPs são guardados apenas como hash irreversível. Arquivos enviados são apagados em poucas horas.",
    }


def delete_account(db: Session, user: User, password: str, provider_cancel=None) -> None:
    with db.begin():
        row = credits.lock_user(db, user.id)
        if not verify_password(row.password_hash, password):
            raise Forbidden("Senha incorreta.", code="wrong_password")
        if row.role == "admin":
            raise AppError("Contas de administrador não podem ser excluídas por aqui.", code="admin_account")
        anon = hashlib.sha256(f"{row.id}:{row.email}".encode()).hexdigest()[:24]
        keys = [k for (k,) in db.execute(select(Upload.storage_key).where(Upload.owner_user_id == row.id))]
        keys += [
            k
            for (k,) in db.execute(
                select(ProcessingJob.output_key).where(
                    ProcessingJob.user_id == row.id, ProcessingJob.output_key.is_not(None)
                )
            )
        ]
        db.execute(
            update(UserSession)
            .where(UserSession.user_id == row.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=clock.now())
        )
        subs = (
            db.execute(
                select(Subscription).where(
                    Subscription.user_id == row.id, Subscription.status.in_(("active", "past_due", "pending"))
                )
            )
            .scalars()
            .all()
        )
        to_cancel = [
            s.provider_preapproval_id for s in subs if s.renewal_mode == "card_auto" and s.provider_preapproval_id
        ]
        for sub in subs:
            sub.status = "canceled"
            sub.canceled_at = clock.now()
        for upload in db.execute(select(Upload).where(Upload.owner_user_id == row.id)).scalars():
            db.delete(upload)
        for inspection in db.execute(select(UrlInspection).where(UrlInspection.owner_user_id == row.id)).scalars():
            db.delete(inspection)
        db.execute(
            update(ProcessingJob)
            .where(ProcessingJob.user_id == row.id)
            .values(output_key=None, input_key=None, input_meta={}, options={})
        )
        row.email = f"excluido-{anon}@invalid.baixeai"
        row.display_name = None
        row.password_hash = hash_password(secrets.token_urlsafe(32))
        row.status = "deleted"
        row.deleted_at = clock.now()
        db.add(
            AuditEvent(
                actor_type="user",
                actor_id=str(row.id),
                action="account_deleted",
                target_type="user",
                target_id=str(row.id),
                metadata_={},
            )
        )
    storage = get_storage()
    for key in keys:
        if key:
            storage.delete(key)
    for pid in to_cancel:
        if provider_cancel:
            with contextlib.suppress(Exception):  # account already anonymized; admin can cancel on MP
                provider_cancel(pid)
