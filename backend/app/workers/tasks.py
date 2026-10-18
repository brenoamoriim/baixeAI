import logging
import uuid

from app.core.db import SessionLocal
from app.services import credits, downloads, jobs, uploads
from app.workers.celery_app import celery

log = logging.getLogger(__name__)


# Engines enforce their own timeouts (sandbox); these Celery limits are only a backstop.
@celery.task(name="jobs.run", soft_time_limit=1000, time_limit=1060)
def run_job(job_id: str) -> None:
    with SessionLocal() as db:
        jobs.run(db, uuid.UUID(job_id))


# ---- worker-download (no database access: plain arguments in, results sent back as tasks) ----


@celery.task(name="download.inspect", soft_time_limit=90, time_limit=120)
def download_inspect(inspection_id: str, url: str, limits: dict) -> None:
    from app.tools.downloader.extractor import ExtractionError
    from app.tools.downloader.worker import extractor_for

    try:
        info = extractor_for(limits).inspect(url)
        result = {"ok": True, "info": info.__dict__}
    except ExtractionError as exc:
        result = {"ok": False, "error_code": exc.code, "message": exc.message}
    except Exception:  # noqa: BLE001
        log.exception("inspect crashed")
        result = {"ok": False, "error_code": "extractor_failed", "message": "Falha ao consultar o link."}
    downloads_inspection_result.apply_async(args=[inspection_id, result], queue="default")


@celery.task(name="download.fetch", soft_time_limit=1500, time_limit=1560)
def download_fetch(job_id: str, url: str, output: str, quality: str, limits: dict, name_hint: str,
                   domain: str) -> None:
    from app.tools.downloader.worker import fetch

    jobs_mark_processing.apply_async(args=[job_id], queue="default")
    result = fetch(job_id, url, output, quality, limits, name_hint,
                   progress=lambda value: downloads.set_progress(job_id, value))
    jobs_finish_remote.apply_async(args=[job_id, result], queue="default")


# ---- default worker (database side) ----


@celery.task(name="downloads.inspection_result")
def downloads_inspection_result(inspection_id: str, result: dict) -> None:
    with SessionLocal() as db:
        downloads.apply_inspection(db, uuid.UUID(inspection_id), result)


@celery.task(name="jobs.mark_processing")
def jobs_mark_processing(job_id: str) -> None:
    with SessionLocal() as db:
        jobs.mark_processing(db, uuid.UUID(job_id))


@celery.task(name="jobs.finish_remote")
def jobs_finish_remote(job_id: str, result: dict) -> None:
    with SessionLocal() as db:
        jobs.finish_remote(db, uuid.UUID(job_id), result)


@celery.task(name="uploads.probe", soft_time_limit=90, time_limit=120)
def probe_upload(upload_id: str) -> None:
    with SessionLocal() as db:
        uploads.probe(db, uuid.UUID(upload_id))


@celery.task(name="maintenance.cleanup_uploads")
def cleanup_uploads() -> int:
    return uploads.cleanup_expired(SessionLocal)


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
