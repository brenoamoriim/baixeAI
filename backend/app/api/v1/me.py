from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core import clock
from app.core.db import get_db
from app.models import Plan, User
from app.services import credits

router = APIRouter(prefix="/me", tags=["me"])


@router.get("")
def me(user: User = Depends(current_user)) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "email_verified": user.email_verified_at is not None,
        "role": user.role,
    }


@router.get("/credits")
def my_credits(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    at = clock.now()
    with db.begin():
        data = credits.balance(db, user, at)
        sub = credits.active_recurring(db, user.id, at)
        plan = db.get(Plan, sub.plan_id) if sub else None
        next_plan = db.get(Plan, sub.next_plan_id) if sub and sub.next_plan_id else None
    return {
        "lifetime": data["lifetime"],
        "email_verified": user.email_verified_at is not None,
        "subscription": {
            "plan": plan.code,
            "plan_name": plan.name,
            "period_end": sub.current_period_end.isoformat(),
            "cancel_at_period_end": sub.cancel_at_period_end,
            "next_plan": next_plan.code if next_plan else None,
        } if sub else None,
        "total_general": data["total_general"],
        "buckets": [
            {
                "kind": b.kind,
                "tool_id": b.tool_id,
                "available": b.available,
                "reserved": b.reserved,
                "expires_at": b.expires_at.isoformat(),
            }
            for b in data["buckets"]
        ],
    }
