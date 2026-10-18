"""Video downloader orchestration. worker-download never touches the database: it receives
plain arguments and reports back through tasks executed by the default worker.

Flow: inspect URL (no charge) -> user picks a REAL option + accepts rights -> job (charge)
-> worker-download fetches through the egress proxy -> finish task commits or refunds.
"""

import contextlib
import logging
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.errors import AppError, NotFound
from app.models import UrlInspection
from app.security import ssrf
from app.security.crypto import keyed_hash
from app.security.rate_limit import get_redis
from app.services.settings import get_setting

log = logging.getLogger(__name__)
INSPECTION_TTL = timedelta(hours=1)


def limits(db: Session) -> dict:
    return {"max_bytes": int(get_setting(db, "download_max_bytes")),
            "max_seconds": int(get_setting(db, "download_max_seconds"))}


def _owner_filter(actor):
    if actor.user_id is not None:
        return UrlInspection.owner_user_id == actor.user_id
    return UrlInspection.owner_anon_hash == keyed_hash(actor.guest_anon_id or "", purpose="guest")


def create_inspection(db: Session, actor, raw_url: str) -> UrlInspection:
    try:
        target = ssrf.validate_url(raw_url)  # early check; the egress proxy re-checks every hop
    except ssrf.UnsafeUrl as exc:
        raise AppError(exc.message, code=exc.code) from None
    lim = limits(db)
    db.commit()
    inspection = UrlInspection(
        id=uuid.uuid4(),
        owner_user_id=actor.user_id,
        owner_anon_hash=None if actor.user_id else keyed_hash(actor.guest_anon_id, purpose="guest"),
        url=target.url,
        domain=ssrf.domain_of(target.url),
        status="probing",
        meta={},
        expires_at=clock.now() + INSPECTION_TTL,
    )
    with db.begin():
        db.add(inspection)
    from app.workers.tasks import download_inspect

    try:
        download_inspect.apply_async(args=[str(inspection.id), target.url, lim], queue="download")
    except Exception:
        log.exception("inspect enqueue failed")
        apply_inspection(db, inspection.id, {"ok": False, "error_code": "unavailable_now",
                                             "message": "Serviço de download indisponível. Tente mais tarde."})
    return inspection


def get_owned(db: Session, actor, inspection_id: uuid.UUID) -> UrlInspection:
    row = db.execute(select(UrlInspection).where(UrlInspection.id == inspection_id, _owner_filter(actor))
                     ).scalar_one_or_none()
    if row is None or row.expires_at <= clock.now():
        raise NotFound("Consulta expirada. Cole o link novamente.", code="inspection_not_found")
    return row


def apply_inspection(db: Session, inspection_id: uuid.UUID, result: dict) -> None:
    if db.in_transaction():
        db.commit()
    with db.begin():
        row = db.get(UrlInspection, inspection_id, with_for_update=True)
        if row is None or row.status != "probing":
            return
        if result.get("ok"):
            row.status = "ready"
            row.meta = result["info"]
        else:
            row.status = "rejected"
            row.error_code = result.get("error_code", "extractor_failed")
            row.error_message = result.get("message", "Não foi possível consultar este link.")[:300]
    record_stat(row.domain, "inspect", "ok" if result.get("ok") else result.get("error_code", "failed"))


# --------------------------------------------------------------------------- observability


def record_stat(domain: str, stage: str, outcome: str) -> None:
    """Success/failure per domain (no URLs, no user data) to notice when the extractor breaks."""
    try:
        client = get_redis()
        key = f"dlstats:{domain}"
        client.hincrby(key, f"{stage}:{outcome}", 1)
        client.expire(key, 60 * 60 * 24 * 30)
        client.sadd("dlstats:domains", domain)
    except Exception:  # noqa: BLE001 - statistics must never break a request
        log.warning("dlstats unavailable")


def stats() -> list[dict]:
    client = get_redis()
    rows = []
    for domain in sorted(client.smembers("dlstats:domains")):
        counters = {k: int(v) for k, v in client.hgetall(f"dlstats:{domain}").items()}
        ok = counters.get("fetch:ok", 0)
        failed = sum(v for k, v in counters.items() if k.startswith("fetch:") and k != "fetch:ok")
        rows.append({"domain": domain, "counters": counters,
                     "fetch_success_rate": round(ok / (ok + failed), 3) if ok + failed else None})
    return rows


# --------------------------------------------------------------------------- progress


def set_progress(job_id: str, value: int) -> None:
    with contextlib.suppress(Exception):  # progress is best-effort, never fails the job
        get_redis().set(f"jobprogress:{job_id}", int(value), ex=3600)


def get_progress(job_id: str) -> int | None:
    try:
        value = get_redis().get(f"jobprogress:{job_id}")
        return int(value) if value is not None else None
    except Exception:  # noqa: BLE001
        return None
