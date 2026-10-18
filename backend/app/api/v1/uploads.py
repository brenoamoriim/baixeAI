import uuid

from fastapi import APIRouter, Depends, Request, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import actor_for, current_user_optional
from app.core.db import get_db
from app.models import Upload, User
from app.security.crypto import keyed_hash
from app.security.rate_limit import hit
from app.services import uploads as upload_service

router = APIRouter(prefix="/uploads", tags=["uploads"])


def _serialize(upload: Upload) -> dict:
    meta = upload.meta or {}
    return {
        "id": str(upload.id),
        "status": upload.status,
        "format": upload.format,
        "category": upload.category,
        "size_bytes": upload.size_bytes,
        "original_name": upload.original_name,
        "error_code": upload.error_code,
        "error_message": upload.error_message,
        "expires_at": upload.expires_at.isoformat(),
        "info": {k: meta[k] for k in ("width", "height", "pages", "duration_seconds", "has_audio", "has_video")
                 if k in meta},
    }


@router.post("", status_code=201)
def create_upload(
    file: UploadFile,
    request: Request,
    response: Response,
    user: User | None = Depends(current_user_optional),
    db: Session = Depends(get_db),
) -> dict:
    actor = actor_for(request, response, user)
    subject = f"u:{user.id}" if user else f"ip:{keyed_hash(actor.ip, purpose='ip')}"
    hit(f"uploads:{subject}", limit=30, window_seconds=600)
    upload = upload_service.create(db, actor, file.file, file.filename)
    db.refresh(upload)  # the probe may already have finished (it runs in a worker)
    return _serialize(upload)


@router.get("/{upload_id}")
def get_upload(
    upload_id: uuid.UUID,
    request: Request,
    response: Response,
    user: User | None = Depends(current_user_optional),
    db: Session = Depends(get_db),
) -> dict:
    upload = upload_service.get_owned(db, actor_for(request, response, user), upload_id)
    return _serialize(upload)
