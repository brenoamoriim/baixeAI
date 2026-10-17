"""Guest (no account) allowance: 1 credit, once. Server-side, no fingerprinting.

Known limitation (docs/architecture/05 §4): clearing cookies and changing IP yields a new
allowance. The per-IP daily cap bounds the abuse.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import InsufficientCredits, RateLimited
from app.models import GuestAllowance
from app.security.crypto import keyed_hash
from app.services.settings import get_setting


def get_or_create_allowance(db: Session, anon_id: str, ip: str, at: datetime) -> GuestAllowance:
    """Find the allowance for this anonymous cookie, or create one if the IP cap allows."""
    anon_hash = keyed_hash(anon_id, purpose="guest")
    existing = db.execute(
        select(GuestAllowance).where(GuestAllowance.anon_id_hash == anon_hash).with_for_update()
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    ip_hash = keyed_hash(ip, purpose="ip")
    # Serialize allowance creation per IP so the daily cap cannot be raced.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"guest-ip:{ip_hash}"})
    day_start, _ = clock.local_day_bounds(clock.local_date(at))
    created_today = db.execute(
        select(func.count())
        .select_from(GuestAllowance)
        .where(GuestAllowance.ip_hash == ip_hash, GuestAllowance.created_at >= day_start)
    ).scalar_one()
    if created_today >= int(get_setting(db, "guest_max_per_ip_per_day")):
        raise RateLimited(
            "Limite de uso sem cadastro atingido nesta rede. Crie uma conta gratuita para continuar."
        )
    db.execute(
        pg_insert(GuestAllowance)
        .values(id=uuid.uuid4(), anon_id_hash=anon_hash, ip_hash=ip_hash, status="available",
                created_at=at)
        .on_conflict_do_nothing(index_elements=["anon_id_hash"])
    )
    return db.execute(
        select(GuestAllowance).where(GuestAllowance.anon_id_hash == anon_hash).with_for_update()
    ).scalar_one()


def reserve(db: Session, allowance: GuestAllowance, *, amount: int, job_id: uuid.UUID) -> None:
    """Caller holds the row lock (from get_or_create_allowance)."""
    if allowance.status != "available":
        raise InsufficientCredits(
            "Você já usou sua ficha gratuita. Crie uma conta para ganhar 5 fichas por dia."
        )
    if amount > int(get_setting(db, "guest_credits")):
        raise InsufficientCredits(
            "Esta operação custa mais fichas do que o uso sem cadastro permite. Crie uma conta."
        )
    allowance.status = "reserved"
    allowance.job_id = job_id


def _locked(db: Session, allowance_id: uuid.UUID) -> GuestAllowance:
    return db.execute(
        select(GuestAllowance).where(GuestAllowance.id == allowance_id).with_for_update()
    ).scalar_one()


def commit(db: Session, allowance_id: uuid.UUID, job_id: uuid.UUID, at: datetime) -> bool:
    allowance = _locked(db, allowance_id)
    if allowance.status != "reserved" or allowance.job_id != job_id:
        return False
    allowance.status = "consumed"
    allowance.consumed_at = at
    return True


def release(db: Session, allowance_id: uuid.UUID, job_id: uuid.UUID) -> bool:
    allowance = _locked(db, allowance_id)
    if allowance.status != "reserved" or allowance.job_id != job_id:
        return False
    allowance.status = "available"
    allowance.job_id = None
    return True
