"""Admin endpoints (RBAC). The full admin panel is Phase 5; this exposes read-only settings."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.db import get_db
from app.models import SystemSetting, User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/settings")
def list_settings(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    rows = db.execute(select(SystemSetting).order_by(SystemSetting.key)).scalars()
    return {"settings": [{"key": r.key, "value": r.value, "description": r.description}
                         for r in rows]}
