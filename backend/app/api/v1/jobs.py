import re
import time
import uuid

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import actor_for, current_user_optional
from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import AppError, NotFound
from app.models import GuestAllowance, ProcessingJob, User
from app.security.crypto import keyed_hash, sign, verify_signature
from app.security.rate_limit import hit
from app.services import jobs as job_service
from app.services.jobs import Actor
from app.storage.base import get_storage

router = APIRouter(prefix="/jobs", tags=["jobs"])

IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9_-]{8,80}$")
FORMAT_RE = r"^[a-z0-9]{1,20}$"


class CreateJob(BaseModel):
    tool_id: str = Field(pattern=r"^[a-z_]{1,40}$")
    input_format: str = Field(pattern=FORMAT_RE)
    output_format: str = Field(pattern=FORMAT_RE)
    options: dict = Field(default_factory=dict)


def _owner_ref(job: ProcessingJob) -> str:
    return f"u:{job.user_id}" if job.user_id else f"g:{job.guest_allowance_id}"


def _is_owner(db: Session, job: ProcessingJob, actor: Actor) -> bool:
    if actor.user_id is not None:
        return job.user_id == actor.user_id
    if job.guest_allowance_id is None or not actor.guest_anon_id:
        return False
    allowance = db.get(GuestAllowance, job.guest_allowance_id)
    return allowance is not None and allowance.anon_id_hash == keyed_hash(
        actor.guest_anon_id, purpose="guest"
    )


def _load_owned(db: Session, job_id: uuid.UUID, actor: Actor) -> ProcessingJob:
    job = db.get(ProcessingJob, job_id)
    # Same 404 for "missing" and "not yours": no IDOR oracle.
    if job is None or not _is_owner(db, job, actor):
        raise NotFound("Processamento não encontrado.")
    return job


def _serialize(job: ProcessingJob) -> dict:
    return {
        "id": str(job.id),
        "tool_id": job.tool_id,
        "status": job.status,
        "progress": job.progress,
        "credit_cost": job.credit_cost,
        "charged_from": job.charged_from,
        "error_code": job.error_code,
        "error_class": job.error_class,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "output_expires_at": job.output_expires_at.isoformat() if job.output_expires_at else None,
        "has_output": job.status == "completed" and job.output_key is not None,
    }


@router.post("/estimate")
def estimate_cost(
    body: CreateJob,
    request: Request,
    response: Response,
    user: User | None = Depends(current_user_optional),
    db: Session = Depends(get_db),
) -> dict:
    """Exact cost the backend will charge (shown before the user confirms)."""
    cost = job_service.estimate(db, actor_for(request, response, user), tool_id=body.tool_id,
                                input_format=body.input_format, output_format=body.output_format,
                                options=body.options)
    return {"cost": cost}


@router.post("", status_code=201)
def create_job(
    body: CreateJob,
    request: Request,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    user: User | None = Depends(current_user_optional),
    db: Session = Depends(get_db),
) -> dict:
    if not IDEMPOTENCY_RE.match(idempotency_key):
        raise AppError("Cabeçalho Idempotency-Key inválido.", code="invalid_idempotency_key")
    actor = actor_for(request, response, user)
    subject = f"u:{user.id}" if user else f"ip:{keyed_hash(actor.ip, purpose='ip')}"
    hit(f"jobs:create:{subject}", limit=30, window_seconds=60)
    job, created = job_service.create_job(
        db,
        actor,
        tool_id=body.tool_id,
        input_format=body.input_format,
        output_format=body.output_format,
        options=body.options,
        idempotency_key=idempotency_key,
    )
    if not created:
        response.status_code = 200
    db.refresh(job)
    return _serialize(job)


@router.get("")
def list_jobs(
    user: User | None = Depends(current_user_optional), db: Session = Depends(get_db)
) -> dict:
    if user is None:
        return {"jobs": []}
    rows = db.execute(
        select(ProcessingJob)
        .where(ProcessingJob.user_id == user.id)
        .order_by(ProcessingJob.created_at.desc())
        .limit(20)
    ).scalars()
    return {"jobs": [_serialize(j) for j in rows]}


@router.get("/{job_id}")
def get_job(
    job_id: uuid.UUID,
    request: Request,
    response: Response,
    user: User | None = Depends(current_user_optional),
    db: Session = Depends(get_db),
) -> dict:
    return _serialize(_load_owned(db, job_id, actor_for(request, response, user)))


@router.post("/{job_id}/download-link")
def download_link(
    job_id: uuid.UUID,
    request: Request,
    response: Response,
    user: User | None = Depends(current_user_optional),
    db: Session = Depends(get_db),
) -> dict:
    job = _load_owned(db, job_id, actor_for(request, response, user))
    if job.status != "completed" or not job.output_key:
        raise NotFound("Arquivo indisponível.", code="output_unavailable")
    expires = int(time.time()) + get_settings().signed_url_ttl_seconds
    signature = sign(f"{job.id}:{expires}:{_owner_ref(job)}")
    return {"url": f"/api/v1/jobs/{job.id}/download?exp={expires}&sig={signature}",
            "expires_at": expires}


@router.get("/{job_id}/download")
def download(
    job_id: uuid.UUID,
    request: Request,
    response: Response,
    exp: int = Query(),
    sig: str = Query(max_length=128),
    user: User | None = Depends(current_user_optional),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Requires BOTH a valid unexpired signature AND the owner's session/guest cookie."""
    job = _load_owned(db, job_id, actor_for(request, response, user))
    if exp < int(time.time()) or not verify_signature(f"{job.id}:{exp}:{_owner_ref(job)}", sig):
        raise NotFound("Link expirado ou inválido.", code="invalid_link")
    if job.status != "completed" or not job.output_key:
        raise NotFound("Arquivo indisponível.", code="output_unavailable")
    try:
        path = get_storage().open_path(job.output_key)
    except FileNotFoundError:
        raise NotFound("Arquivo indisponível.", code="output_unavailable") from None
    return FileResponse(
        path,
        filename=job.output_filename or "arquivo",
        media_type="application/octet-stream",
        headers={"Cache-Control": "private, no-store"},
    )
