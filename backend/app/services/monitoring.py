"""Operational health: disk, queues, failures. Alerts go by e-mail to ALERT_EMAIL, at most once per hour per kind.

Free by design: no external monitoring service is required (an external uptime check of /healthz is recommended
in docs/OPERACAO.md, because a dead server cannot send its own alert).
"""

import logging
import shutil
from datetime import timedelta

from sqlalchemy import func, select

from app.core import clock
from app.core.config import get_settings
from app.models import Payment, ProcessingJob
from app.security.rate_limit import get_redis

log = logging.getLogger("app.monitoring")

QUEUES = ("default", "light", "media", "ai", "download")
DISK_ALERT_PERCENT = 80
QUEUE_ALERT_LENGTH = 50
FAILURE_ALERT_COUNT = 20  # system failures in the last hour


def disk_usage() -> dict:
    usage = shutil.disk_usage(get_settings().storage_local_root)
    return {"total_bytes": usage.total, "free_bytes": usage.free,
            "used_percent": round(100 * (usage.total - usage.free) / usage.total, 1) if usage.total else 0.0}


def queue_lengths() -> dict:
    redis = get_redis()
    return {q: int(redis.llen(q)) for q in QUEUES}


def snapshot(db) -> dict:
    since = clock.now() - timedelta(hours=1)
    system_failures = db.execute(
        select(func.count()).select_from(ProcessingJob).where(
            ProcessingJob.finished_at >= since, ProcessingJob.status == "failed",
            ProcessingJob.error_class.in_(("system", "timeout")))
    ).scalar_one()
    stale_pending = db.execute(
        select(func.count()).select_from(Payment).where(
            Payment.status == "pending", Payment.created_at < clock.now() - timedelta(days=2))
    ).scalar_one()
    return {"disk": disk_usage(), "queues": queue_lengths(), "system_failures_1h": int(system_failures),
            "payments_pending_over_2d": int(stale_pending)}


def problems(snap: dict) -> list[tuple[str, str]]:
    found = []
    if snap["disk"]["used_percent"] >= DISK_ALERT_PERCENT:
        found.append(("disk", f"Disco em {snap['disk']['used_percent']}% (limite {DISK_ALERT_PERCENT}%)."))
    for queue, length in snap["queues"].items():
        if length >= QUEUE_ALERT_LENGTH:
            found.append((f"queue:{queue}", f"Fila '{queue}' com {length} tarefas esperando."))
    if snap["system_failures_1h"] >= FAILURE_ALERT_COUNT:
        found.append(("failures", f"{snap['system_failures_1h']} falhas de sistema na última hora."))
    return found


def alert(kind: str, message: str) -> bool:
    """Log at ERROR and e-mail ALERT_EMAIL, throttled to once per hour per kind. Never raises."""
    log.error("ALERT %s: %s", kind, message, extra={"alert": kind})
    try:
        if not get_redis().set(f"alert:{kind}", "1", nx=True, ex=3600):
            return False
        to = get_settings().alert_email
        if to:
            from app.services import email

            email.send(to, f"[BaixeAI] Alerta: {kind}", f"{message}\n\nHorário (UTC): {clock.now().isoformat()}")
        return True
    except Exception:  # noqa: BLE001 - alerting must never break the caller
        log.exception("alert delivery failed")
        return False
