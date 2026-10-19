from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import current_user, current_user_optional
from app.core import clock
from app.core.config import get_settings
from app.core.db import get_db
from app.models import Plan, User
from app.security.crypto import token_hash
from app.security.rate_limit import hit
from app.services import account, credits

router = APIRouter(prefix="/me", tags=["me"])


def _public(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "email_verified": user.email_verified_at is not None,
        "role": user.role,
    }


@router.get("")
def me(user: User = Depends(current_user)) -> dict:
    return _public(user)


@router.get("/session")
def session(user: User | None = Depends(current_user_optional)) -> dict:
    """Header/session probe: 200 for visitors too (no 401 noise in the browser console)."""
    return {"user": _public(user) if user else None}


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
        }
        if sub
        else None,
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


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class DeleteAccount(BaseModel):
    password: str = Field(min_length=1, max_length=256)
    confirm: str = Field(pattern=r"^EXCLUIR$")


@router.post("/password")
def change_password(
    body: PasswordChange, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    hit(f"password:u:{user.id}", limit=5, window_seconds=900)
    token = request.cookies.get(get_settings().session_cookie_name)
    account.change_password(db, user, body.current_password, body.new_password, token_hash(token) if token else None)
    return {"message": "Senha alterada. Outros dispositivos foram desconectados."}


@router.get("/export")
def export(user: User = Depends(current_user), db: Session = Depends(get_db)) -> JSONResponse:
    hit(f"export:u:{user.id}", limit=5, window_seconds=3600)
    return JSONResponse(
        account.export_data(db, user),
        headers={
            "Content-Disposition": 'attachment; filename="meus-dados-baixeai.json"',
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/delete")
def delete(
    body: DeleteAccount, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    hit(f"delete:u:{user.id}", limit=5, window_seconds=900)

    def cancel(pid: str) -> None:
        from app.payments import get_provider

        get_provider().cancel_subscription(pid)

    account.delete_account(db, user, body.password, provider_cancel=cancel)
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    return {"message": "Conta excluída. Seus dados pessoais foram anonimizados."}
