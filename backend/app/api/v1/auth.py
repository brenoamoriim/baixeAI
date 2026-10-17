import secrets

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import client_ip, current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.models import User
from app.security.crypto import keyed_hash
from app.security.rate_limit import hit
from app.services import auth

router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_REGISTER = "Se o e-mail puder ser usado, enviamos um link de confirmação."
GENERIC_FORGOT = "Se houver uma conta com este e-mail, enviamos um link para redefinir a senha."


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class EmailOnly(BaseModel):
    email: EmailStr


class TokenOnly(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class ResetPassword(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=1, max_length=256)


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.get("/csrf")
def csrf(request: Request, response: Response) -> dict:
    """Issue the CSRF cookie (double-submit). The frontend echoes it in X-CSRF-Token."""
    settings = get_settings()
    token = request.cookies.get(settings.csrf_cookie_name) or secrets.token_urlsafe(32)
    response.set_cookie(
        settings.csrf_cookie_name, token, httponly=False, secure=settings.cookie_secure,
        samesite="lax", path="/", max_age=60 * 60 * 24 * 7,
    )
    return {"csrf_token": token}


@router.post("/register", status_code=202)
def register(body: Credentials, request: Request, db: Session = Depends(get_db)) -> dict:
    hit(f"register:ip:{keyed_hash(client_ip(request), purpose='ip')}", limit=5, window_seconds=3600)
    auth.register(db, body.email, body.password, client_ip(request))
    return {"message": GENERIC_REGISTER}


@router.post("/login")
def login(body: Credentials, request: Request, response: Response,
          db: Session = Depends(get_db)) -> dict:
    ip = client_ip(request)
    hit(f"login:ip:{keyed_hash(ip, purpose='ip')}", limit=20, window_seconds=900)
    hit(f"login:email:{keyed_hash(body.email.lower(), purpose='email')}", limit=8,
        window_seconds=900)
    token = auth.login(db, body.email, body.password, ip, request.headers.get("user-agent"))
    _set_session_cookie(response, token)
    return {"message": "Login realizado."}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    auth.logout(db, request.cookies.get(settings.session_cookie_name))
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"message": "Você saiu da conta."}


@router.post("/verify-email")
def verify_email(body: TokenOnly, request: Request, db: Session = Depends(get_db)) -> dict:
    hit(f"verify:ip:{keyed_hash(client_ip(request), purpose='ip')}", limit=20, window_seconds=3600)
    auth.verify_email(db, body.token)
    return {"message": "E-mail confirmado."}


@router.post("/resend-verification", status_code=202)
def resend_verification(user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    hit(f"resend:user:{user.id}", limit=3, window_seconds=3600)
    auth.resend_verification(db, user)
    return {"message": "Se necessário, enviamos um novo link de confirmação."}


@router.post("/forgot-password", status_code=202)
def forgot_password(body: EmailOnly, request: Request, db: Session = Depends(get_db)) -> dict:
    hit(f"forgot:ip:{keyed_hash(client_ip(request), purpose='ip')}", limit=5, window_seconds=3600)
    hit(f"forgot:email:{keyed_hash(body.email.lower(), purpose='email')}", limit=3,
        window_seconds=3600)
    auth.request_password_reset(db, body.email, client_ip(request))
    return {"message": GENERIC_FORGOT}


@router.post("/reset-password")
def reset_password(body: ResetPassword, request: Request, db: Session = Depends(get_db)) -> dict:
    hit(f"reset:ip:{keyed_hash(client_ip(request), purpose='ip')}", limit=10, window_seconds=3600)
    auth.reset_password(db, body.token, body.password, client_ip(request))
    return {"message": "Senha alterada. Entre novamente."}
