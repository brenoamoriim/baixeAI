from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import FeatureFlag
from app.services.settings import get_setting

router = APIRouter(tags=["site"])


@router.get("/site-config")
def site_config(db: Session = Depends(get_db)) -> dict:
    """Public, non-secret configuration for the frontend (ads only when enabled AND configured)."""
    flag = db.get(FeatureFlag, "ads_enabled")
    client = get_setting(db, "adsense_client_id")
    slots = get_setting(db, "adsense_slots") or {}
    enabled = bool(flag and flag.enabled and client)
    return {"ads": {"enabled": enabled, "client": client if enabled else None, "slots": slots if enabled else {}},
            # ads.txt must exist before AdSense approval, so it only depends on the (public) publisher id
            "ads_txt_client": client,
            "support_email": get_setting(db, "support_email")}
