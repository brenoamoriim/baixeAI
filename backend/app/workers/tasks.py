import logging
import uuid

from app.core.db import SessionLocal
from app.services import credits, jobs
from app.workers.celery_app import celery

log = logging.getLogger(__name__)


@celery.task(name="jobs.run")
def run_job(job_id: str) -> None:
    with SessionLocal() as db:
        jobs.run(db, uuid.UUID(job_id))


@celery.task(name="maintenance.expire_buckets")
def expire_buckets() -> int:
    return credits.expire_due_buckets(SessionLocal)


@celery.task(name="maintenance.sweep_stuck_jobs")
def sweep_stuck_jobs() -> int:
    return jobs.sweep_stuck_jobs(SessionLocal)


@celery.task(name="maintenance.cleanup_outputs")
def cleanup_outputs() -> int:
    return jobs.cleanup_expired_outputs(SessionLocal)


@celery.task(name="maintenance.ledger_reconciliation")
def ledger_reconciliation() -> int:
    with SessionLocal() as db:
        mismatches = credits.ledger_mismatches(db)
    if mismatches:
        # Alert only; never auto-fix the ledger (docs/architecture/04 §3).
        log.error("ledger mismatch", extra={"buckets": [str(b) for b in mismatches]})
    return len(mismatches)
