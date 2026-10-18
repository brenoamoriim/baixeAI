import uuid

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import actor_for, current_user_optional, require_admin
from app.core.db import get_db
from app.models import UrlInspection, User
from app.security.crypto import keyed_hash
from app.security.rate_limit import hit
from app.services import downloads

router = APIRouter(prefix="/downloads", tags=["downloads"])
admin_router = APIRouter(prefix="/admin", tags=["admin"])


class InspectBody(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


def _serialize(row: UrlInspection) -> dict:
    meta = row.meta or {}
    return {
        "id": str(row.id),
        "status": row.status,
        "domain": row.domain,
        "error_code": row.error_code,
        "error_message": row.error_message,
        "title": meta.get("title"),
        "duration_seconds": meta.get("duration_seconds"),
        "heights": meta.get("heights", []),
        "has_audio": meta.get("has_audio"),
        "has_video": meta.get("has_video"),
        "extractor": meta.get("extractor"),
    }


@router.post("/inspect", status_code=201)
def inspect(body: InspectBody, request: Request, response: Response,
            user: User | None = Depends(current_user_optional), db: Session = Depends(get_db)) -> dict:
    """Validate the URL (SSRF) and ask the extractor for the REAL options. Never charges."""
    actor = actor_for(request, response, user)
    subject = f"u:{user.id}" if user else f"ip:{keyed_hash(actor.ip, purpose='ip')}"
    hit(f"downloads:inspect:{subject}", limit=20, window_seconds=600)
    row = downloads.create_inspection(db, actor, body.url)
    db.refresh(row)
    return _serialize(row)


@router.get("/inspections/{inspection_id}")
def get_inspection(inspection_id: uuid.UUID, request: Request, response: Response,
                   user: User | None = Depends(current_user_optional), db: Session = Depends(get_db)) -> dict:
    return _serialize(downloads.get_owned(db, actor_for(request, response, user), inspection_id))


@admin_router.get("/download-stats")
def download_stats(_: User = Depends(require_admin)) -> dict:
    return {"domains": downloads.stats()}
