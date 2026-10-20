"""Job lifecycle: validate -> price -> reserve -> queue -> run -> commit/release.

Refund policy (PRD §2): system failure and timeout release the credits; invalid input found
during processing commits them; there is no user cancellation (D12).
"""

import logging
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.errors import AppError, FairUseLimit, NotFound, RateLimited
from app.models import (
    CreditCostRule,
    CreditReservation,
    GuestAllowance,
    ProcessingJob,
    TermsAcceptance,
    ToolCapability,
    ToolDefinition,
    UsageRecord,
)
from app.security.crypto import keyed_hash
from app.services import credits, downloads, guests, uploads
from app.services.settings import get_setting
from app.storage.base import get_storage, new_key
from app.tools.base import ToolSystemError, ToolUserError
from app.tools.registry import get_handler

log = logging.getLogger(__name__)
ACTIVE_STATUSES = ("queued", "processing")


@dataclass
class Actor:
    """Who is asking: a logged-in user, or a guest identified by an anonymous cookie."""

    user_id: uuid.UUID | None = None
    guest_anon_id: str | None = None
    ip: str = "0.0.0.0"  # noqa: S104 - placeholder, never used to bind


# --------------------------------------------------------------------------- catalog / pricing


def available_capability(
    db: Session, tool_id: str, input_format: str, output_format: str
) -> tuple[ToolDefinition, ToolCapability]:
    tool = db.get(ToolDefinition, tool_id)
    handler = get_handler(tool_id)
    if tool is None or not tool.enabled or handler is None:
        raise NotFound("Ferramenta indisponível.")
    if tool.dev_only and get_settings().is_production:
        raise NotFound("Ferramenta indisponível.")
    capability = db.execute(
        select(ToolCapability).where(
            ToolCapability.tool_id == tool_id,
            ToolCapability.input_format == input_format,
            ToolCapability.output_format == output_format,
            ToolCapability.status == "available",
        )
    ).scalar_one_or_none()
    if capability is None:
        raise NotFound("Combinação de formatos indisponível.", code="capability_unavailable")
    return tool, capability


def credit_cost(
    db: Session, tool: ToolDefinition, capability: ToolCapability, meta: dict
) -> int:
    """Most specific active rule wins (D1); otherwise the tool's base cost."""
    rules = db.execute(
        select(CreditCostRule)
        .where(CreditCostRule.tool_id == tool.id, CreditCostRule.active.is_(True))
        .order_by(CreditCostRule.priority.desc())
    ).scalars()
    duration = meta.get("duration_seconds")
    for rule in rules:
        if rule.category is not None and rule.category != capability.category:
            continue
        if rule.min_duration_seconds is not None and (
            duration is None or duration < rule.min_duration_seconds
        ):
            continue
        return rule.cost
    return tool.credit_cost


# --------------------------------------------------------------------------- creation


@dataclass
class Prepared:
    """Everything decided BEFORE charging: validated options, price, queue and input file."""

    tool: ToolDefinition
    capability: ToolCapability
    options: dict
    cost: int
    queue: str
    input_key: str | None = None
    input_meta: dict | None = None
    terms: tuple[str, str] | None = None  # (document, version) accepted with this job


def _ready_upload(db: Session, actor: Actor, raw_id) -> "uploads.Upload":
    try:
        upload_id = uuid.UUID(str(raw_id))
    except ValueError:
        raise AppError("Envie um arquivo primeiro.", code="upload_required") from None
    upload = uploads.get_owned(db, actor, upload_id)
    if upload.status == "probing":
        raise AppError("O arquivo ainda está sendo analisado. Aguarde.", code="upload_not_ready")
    if upload.status != "ready":
        raise AppError(upload.error_message or "Arquivo recusado.", code=upload.error_code or "upload_rejected")
    return upload


def prepare(db: Session, actor: Actor, tool_id: str, input_format: str, output_format: str,
            options: dict, *, for_estimate: bool = False) -> Prepared:
    tool, capability = available_capability(db, tool_id, input_format, output_format)
    handler = get_handler(tool_id)
    upload = None
    inspection = None
    extra_meta: dict[str, dict] = {}
    extra_keys: dict[str, str] = {}
    if getattr(handler, "requires_inspection", False):
        try:
            inspection_id = uuid.UUID(str(options.get("inspection_id")))
        except ValueError:
            raise AppError("Cole o link do vídeo primeiro.", code="inspection_required") from None
        inspection = downloads.get_owned(db, actor, inspection_id)
        if inspection.status == "probing":
            raise AppError("Ainda consultando o link. Aguarde.", code="inspection_not_ready")
        if inspection.status != "ready":
            raise AppError(inspection.error_message or "Link recusado.",
                           code=inspection.error_code or "inspection_rejected")
    if handler.requires_upload:
        upload = _ready_upload(db, actor, options.get("upload_id"))
        if upload.format != input_format:
            raise AppError("O formato escolhido não corresponde ao conteúdo do arquivo.", code="format_mismatch")
    for field in getattr(handler, "extra_uploads", ()):
        if options.get(field) is None and for_estimate:
            continue
        extra = _ready_upload(db, actor, options.get(field))
        extra_meta[field] = {**extra.meta, "format": extra.format}
        extra_keys[field] = extra.storage_key
    terms = getattr(handler, "required_terms", None)
    if terms and not for_estimate and options.get("accept_rights") is not True:
        raise AppError("Confirme que você tem direito de editar esta imagem.", code="rights_not_accepted")
    upload_meta = {**upload.meta, "extra": extra_meta} if upload else (inspection.meta if inspection else None)
    if for_estimate and getattr(handler, "extra_uploads", ()):
        options = {**options, "accept_rights": True}  # estimate: price only, terms checked on create
        if not extra_meta:
            cost = credit_cost(db, tool, capability, handler.metadata(options, upload_meta))
            return Prepared(tool=tool, capability=capability, options={}, cost=cost,
                            queue=handler.queue_for(capability.category) or tool.queue)
    clean_options = handler.validate_options(input_format, output_format, options, upload_meta)
    cost = credit_cost(db, tool, capability, handler.metadata(clean_options, upload_meta))
    prepared = Prepared(tool=tool, capability=capability, options=clean_options, cost=cost,
                        queue=handler.queue_for(capability.category) or tool.queue)
    if upload is not None:
        prepared.input_key = upload.storage_key
        prepared.input_meta = {**upload.meta, "original_name": upload.original_name,
                               "format": upload.format, "size_bytes": upload.size_bytes,
                               "extra_keys": extra_keys}
    if inspection is not None:
        prepared.input_meta = {**inspection.meta, "url": inspection.url, "domain": inspection.domain,
                               "original_name": f"{inspection.meta.get('title', 'video')}.x",
                               "limits": downloads.limits(db)}
    prepared.terms = terms
    return prepared


def estimate(db: Session, actor: Actor, *, tool_id: str, input_format: str, output_format: str,
             options: dict) -> int:
    """Cost the backend WILL charge for this request (same rules as create_job)."""
    with db.begin():
        return prepare(db, actor, tool_id, input_format, output_format, options, for_estimate=True).cost


def create_job(
    db: Session,
    actor: Actor,
    *,
    tool_id: str,
    input_format: str,
    output_format: str,
    options: dict,
    idempotency_key: str,
) -> tuple[ProcessingJob, bool]:
    """Create (or return the existing) job for this idempotency key. Returns (job, created)."""
    at = clock.now()
    try:
        with db.begin():
            # Validation and pricing happen before any reservation: invalid input costs nothing.
            prepared = prepare(db, actor, tool_id, input_format, output_format, options)
            if actor.user_id is not None:
                job, created = _create_for_user(db, actor, prepared, idempotency_key, at)
            else:
                job, created = _create_for_guest(db, actor, prepared, idempotency_key, at)
    except IntegrityError:
        # A concurrent request with the same idempotency key won the race.
        db.rollback()
        job = _find_existing(db, actor, idempotency_key)
        db.commit()
        if job is None:
            raise
        return job, False

    if created:
        dispatch(db, job)
    return job, created


def _find_existing(db: Session, actor: Actor, key: str) -> ProcessingJob | None:
    if actor.user_id is not None:
        return db.execute(
            select(ProcessingJob).where(
                ProcessingJob.user_id == actor.user_id, ProcessingJob.idempotency_key == key
            )
        ).scalar_one_or_none()
    return db.execute(
        select(ProcessingJob)
        .join(GuestAllowance, GuestAllowance.id == ProcessingJob.guest_allowance_id)
        .where(
            GuestAllowance.anon_id_hash == keyed_hash(actor.guest_anon_id, purpose="guest"),
            ProcessingJob.idempotency_key == key,
        )
    ).scalar_one_or_none()


def _new_job(p: Prepared, key: str, charged_from: str, **owner) -> ProcessingJob:
    return ProcessingJob(
        id=uuid.uuid4(),
        tool_id=p.tool.id,
        capability_id=p.capability.id,
        status="queued",
        charged_from=charged_from,
        credit_cost=p.cost,
        idempotency_key=key,
        options=p.options,
        input_key=p.input_key,
        input_meta=p.input_meta or {},
        queue=p.queue,
        **owner,
    )


def _create_for_user(db, actor, p: Prepared, key, at):
    user = credits.lock_user(db, actor.user_id)
    existing = _find_existing(db, actor, key)
    if existing is not None:
        return existing, False
    if user.status != "active":
        raise AppError("Conta indisponível.", code="account_inactive")

    active_jobs = db.execute(
        select(func.count())
        .select_from(ProcessingJob)
        .where(ProcessingJob.user_id == user.id, ProcessingJob.status.in_(ACTIVE_STATUSES))
    ).scalar_one()

    if credits.has_lifetime(db, user.id):
        _check_lifetime_fair_use(db, user.id, active_jobs, at)
        job = _new_job(p, key, "lifetime", user_id=user.id)
        db.add(job)
        db.flush()
        _record_terms(db, p, job, actor, user_id=user.id)
        return job, True

    if active_jobs >= int(get_setting(db, "max_pending_jobs_per_user")):
        raise RateLimited("Você já tem processamentos em andamento. Aguarde terminarem.")
    job = _new_job(p, key, "credits", user_id=user.id)
    db.add(job)
    db.flush()
    _record_terms(db, p, job, actor, user_id=user.id)
    credits.reserve(db, user, tool_id=p.tool.id, amount=p.cost, job_id=job.id,
                    idempotency_key=key, at=at)
    return job, True


def _record_terms(db: Session, p: Prepared, job: ProcessingJob, actor: Actor, **owner) -> None:
    """Rights declaration recorded in the same transaction as the charge (PRD §6.4)."""
    if p.terms is None:
        return
    document, version = p.terms
    db.add(TermsAcceptance(document=document, version=version, job_id=job.id,
                           ip_hash=keyed_hash(actor.ip, purpose="ip"), **owner))


def _check_lifetime_fair_use(db: Session, user_id: uuid.UUID, active_jobs: int, at: datetime):
    if active_jobs >= int(get_setting(db, "lifetime_max_concurrent_jobs")):
        raise FairUseLimit("Limite de processamentos simultâneos do plano vitalício atingido.")
    day_start, _ = clock.local_day_bounds(clock.local_date(at))
    today = db.execute(
        select(func.count())
        .select_from(ProcessingJob)
        .where(
            ProcessingJob.user_id == user_id,
            ProcessingJob.created_at >= day_start,
            ProcessingJob.status != "failed",
        )
    ).scalar_one()
    if today >= int(get_setting(db, "lifetime_daily_cap")):
        raise FairUseLimit("Limite diário de uso justo do plano vitalício atingido.")


def _create_for_guest(db, actor, p: Prepared, key, at):
    if not actor.guest_anon_id:
        raise AppError("Sessão de visitante ausente.", code="guest_cookie_missing")
    allowance = guests.get_or_create_allowance(db, actor.guest_anon_id, actor.ip, at)
    existing = db.execute(
        select(ProcessingJob).where(
            ProcessingJob.guest_allowance_id == allowance.id, ProcessingJob.idempotency_key == key
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False
    job = _new_job(p, key, "guest", guest_allowance_id=allowance.id)
    guests.reserve(db, allowance, amount=p.cost, job_id=job.id)
    db.add(job)
    db.flush()
    _record_terms(db, p, job, actor, guest_allowance_id=allowance.id)
    return job, True


def _remote_args(db: Session, job: ProcessingJob) -> list:
    capability = db.get(ToolCapability, job.capability_id)
    meta = job.input_meta
    return [str(job.id), meta["url"], capability.output_format, job.options.get("quality", "best"),
            meta["limits"], meta.get("original_name", "video.x"), meta.get("domain", "")]


def job_spec(db: Session, job: ProcessingJob) -> dict:
    """Everything an engine worker needs, as plain data: engine workers have no database access."""
    capability = db.get(ToolCapability, job.capability_id)
    return {
        "job_id": str(job.id),
        "tool_id": job.tool_id,
        "input_format": capability.input_format,
        "output_format": capability.output_format,
        "options": dict(job.options),
        "input_key": job.input_key,
        "input_meta": dict(job.input_meta),
    }


def dispatch(db: Session, job: ProcessingJob) -> None:
    from app.workers.tasks import download_fetch, execute_job

    handler = get_handler(job.tool_id)
    try:
        if getattr(handler, "remote_queue", None):
            result = download_fetch.apply_async(args=_remote_args(db, job), queue=handler.remote_queue)
        else:
            result = execute_job.apply_async(args=[job_spec(db, job)], queue=job.queue)
    except Exception:
        log.exception("enqueue failed", extra={"job_id": str(job.id)})
        fail_job(db, job.id, error_class="system", error_code="enqueue_failed")
        raise AppError("Não foi possível iniciar o processamento. Tente novamente.",
                       code="enqueue_failed") from None
    if result is not None and getattr(result, "id", None):
        if db.in_transaction():
            db.commit()  # close the reads done while building the task arguments
        with db.begin():
            locked = db.get(ProcessingJob, job.id, with_for_update=True)
            if locked.task_id is None:
                locked.task_id = result.id


# --------------------------------------------------------------------------- execution


def execute_spec(spec: dict) -> dict:
    """Engine-worker side (NO database): run the tool and store the output. Returns the outcome as data;
    the default worker applies it (commit or refund) with `finish_engine`."""
    job_id = spec["job_id"]
    handler = get_handler(spec["tool_id"])
    input_format, output_format = spec["input_format"], spec["output_format"]
    input_meta = dict(spec["input_meta"])
    work_dir = Path(tempfile.mkdtemp(prefix="job-"))
    try:
        if handler is None:
            raise ToolSystemError("handler_missing")
        input_path = None
        if spec["input_key"]:
            input_path = work_dir / f"input.{input_format}"
            try:
                shutil.copyfile(get_storage().open_path(spec["input_key"]), input_path)
            except (FileNotFoundError, ValueError):
                raise ToolSystemError("input_missing") from None
        extra_paths = {}
        for field, key in input_meta.get("extra_keys", {}).items():
            extra_paths[field] = work_dir / f"{field}.{key.rsplit('.', 1)[-1]}"
            try:
                shutil.copyfile(get_storage().open_path(key), extra_paths[field])
            except (FileNotFoundError, ValueError):
                raise ToolSystemError("input_missing") from None
        input_meta["extra_paths"] = extra_paths
        result = handler.execute(input_format, output_format, dict(spec["options"]), work_dir, input_path,
                                 input_meta)
        key = new_key(f"jobs/{uuid.UUID(job_id).hex}", result.output_path.suffix.lstrip("."))
        get_storage().save_file(key, result.output_path)
        return {"ok": True, "key": key, "filename": result.filename}
    except ToolUserError as exc:
        return {"ok": False, "error_class": "user_input", "error_code": exc.code}
    except ToolSystemError as exc:
        return {"ok": False, "error_class": "system", "error_code": exc.code}
    except (TimeoutError, SoftTimeLimitExceeded):
        return {"ok": False, "error_class": "timeout", "error_code": "time_limit"}
    except Exception:
        log.exception("job crashed", extra={"job_id": job_id})
        return {"ok": False, "error_class": "system", "error_code": "unexpected"}
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


ERROR_CLASSES = ("user_input", "system", "timeout")


def finish_engine(db: Session, job_id: uuid.UUID, result: dict) -> None:
    """Default-worker side: apply an engine outcome exactly once (a redelivered task is a no-op).
    The outcome comes from a less trusted worker, so it is validated, never used as-is."""
    mark_processing(db, job_id)
    if result.get("ok") is True and isinstance(result.get("key"), str):
        key = result["key"]
        if not key.startswith(f"jobs/{job_id.hex}/") or ".." in key:
            fail_job(db, job_id, error_class="system", error_code="invalid_output")
            return
        complete_job(db, job_id, output_key=key, filename=str(result.get("filename") or "arquivo")[:200])
    else:
        error_class = result.get("error_class")
        error_code = str(result.get("error_code") or "unexpected")[:60]
        fail_job(db, job_id, error_class=error_class if error_class in ERROR_CLASSES else "system",
                 error_code=error_code)
        if error_code == "unexpected":
            from app.services import monitoring

            monitoring.alert("engine_crash", f"Falha inesperada num motor (job {job_id}). Ver logs dos workers.")


def _lock_owner_then_job(db: Session, job_id: uuid.UUID) -> ProcessingJob | None:
    owner = db.execute(
        select(ProcessingJob.user_id).where(ProcessingJob.id == job_id)
    ).scalar_one_or_none()
    if owner is not None:
        credits.lock_user(db, owner)
    return db.get(ProcessingJob, job_id, with_for_update=True)


def _reservation_id(db: Session, job_id: uuid.UUID) -> uuid.UUID | None:
    return db.execute(
        select(CreditReservation.id).where(CreditReservation.job_id == job_id)
    ).scalar_one_or_none()


def complete_job(db: Session, job_id: uuid.UUID, *, output_key: str, filename: str) -> None:
    at = clock.now()
    with db.begin():
        job = _lock_owner_then_job(db, job_id)
        if job is None or job.status not in ACTIVE_STATUSES:
            return
        _settle(db, job, at, refund=False)
        job.status = "completed"
        job.progress = 100
        job.output_key = output_key
        job.output_filename = filename
        job.finished_at = at
        job.output_expires_at = at + timedelta(hours=get_settings().file_retention_hours)
        db.add(
            UsageRecord(
                user_id=job.user_id,
                guest_allowance_id=job.guest_allowance_id,
                tool_id=job.tool_id,
                job_id=job.id,
                credits_charged=0 if job.charged_from == "lifetime" else job.credit_cost,
                charged_from=job.charged_from,
                duration_ms=int((at - job.started_at).total_seconds() * 1000)
                if job.started_at
                else None,
            )
        )


def fail_job(db: Session, job_id: uuid.UUID, *, error_class: str, error_code: str) -> None:
    at = clock.now()
    with db.begin():
        job = _lock_owner_then_job(db, job_id)
        if job is None or job.status not in ACTIVE_STATUSES:
            return
        refund = error_class in ("system", "timeout")
        _settle(db, job, at, refund=refund)
        job.status = "failed"
        job.error_class = error_class
        job.error_code = error_code
        job.finished_at = at
        if not refund:
            db.add(
                UsageRecord(
                    user_id=job.user_id,
                    guest_allowance_id=job.guest_allowance_id,
                    tool_id=job.tool_id,
                    job_id=job.id,
                    credits_charged=0 if job.charged_from == "lifetime" else job.credit_cost,
                    charged_from=job.charged_from,
                )
            )


def _settle(db: Session, job: ProcessingJob, at: datetime, *, refund: bool) -> None:
    if job.charged_from == "credits":
        reservation_id = _reservation_id(db, job.id)
        if refund:
            credits.release(db, reservation_id, at=at, reason=job.error_code or "failure")
        else:
            credits.commit(db, reservation_id, at=at)
    elif job.charged_from == "guest":
        if refund:
            guests.release(db, job.guest_allowance_id, job.id)
        else:
            guests.commit(db, job.guest_allowance_id, job.id, at)


def mark_processing(db: Session, job_id: uuid.UUID) -> None:
    with db.begin():
        job = db.get(ProcessingJob, job_id, with_for_update=True)
        if job is not None and job.status == "queued":
            job.status = "processing"
            job.started_at = clock.now()


def finish_remote(db: Session, job_id: uuid.UUID, result: dict) -> None:
    """Apply worker-download's outcome: commit on success, refund on system failure/timeout."""
    finish_engine(db, job_id, result if result.get("ok") else {"error_code": "extractor_failed", **result})
    job = db.get(ProcessingJob, job_id)
    if job is not None:
        downloads.record_stat(job.input_meta.get("domain", "?"), "fetch",
                              "ok" if result.get("ok") else result.get("error_code", "failed"))


# --------------------------------------------------------------------------- maintenance


def sweep_stuck_jobs(db_factory, at: datetime | None = None) -> int:
    """Jobs that never finished (dead worker) are failed as a system error -> refund."""
    at = at or clock.now()
    with db_factory() as db:
        limit = int(get_setting(db, "job_stuck_after_seconds"))
        stuck = db.execute(
            select(ProcessingJob.id).where(
                ProcessingJob.status.in_(ACTIVE_STATUSES),
                ProcessingJob.created_at < at - timedelta(seconds=limit),
            )
        ).scalars().all()
    for job_id in stuck:
        with db_factory() as db:
            fail_job(db, job_id, error_class="system", error_code="stuck")
    return len(stuck)


def cleanup_expired_outputs(db_factory, at: datetime | None = None) -> int:
    at = at or clock.now()
    with db_factory() as db:
        due = db.execute(
            select(ProcessingJob.id).where(
                ProcessingJob.status == "completed", ProcessingJob.output_expires_at <= at
            )
        ).scalars().all()
    storage = get_storage()
    for job_id in due:
        with db_factory() as db, db.begin():
            job = db.get(ProcessingJob, job_id, with_for_update=True)
            if job.status != "completed":
                continue
            if job.output_key:
                storage.delete(job.output_key)
            job.status = "expired"
    return len(due)
