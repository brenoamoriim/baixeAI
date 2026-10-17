import secrets

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import Forbidden, Unauthorized
from app.models import User
from app.services import auth
from app.services.jobs import Actor


def client_ip(request: Request) -> str:
    """Client IP. X-Forwarded-For is trusted only for the configured number of proxy hops."""
    hops = get_settings().trusted_proxy_hops
    forwarded = request.headers.get("x-forwarded-for")
    if hops > 0 and forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
    return request.client.host if request.client else "0.0.0.0"  # noqa: S104


def current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    return auth.resolve_session(db, request.cookies.get(get_settings().session_cookie_name))


def current_user(user: User | None = Depends(current_user_optional)) -> User:
    if user is None:
        raise Unauthorized("Entre na sua conta para continuar.")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise Forbidden("Acesso restrito.")
    return user


def actor_for(request: Request, response: Response, user: User | None) -> Actor:
    """Logged-in user, or a guest identified by an HttpOnly anonymous cookie (set if missing)."""
    if user is not None:
        return Actor(user_id=user.id, ip=client_ip(request))
    settings = get_settings()
    anon = request.cookies.get(settings.guest_cookie_name)
    if not anon or len(anon) > 100:
        anon = secrets.token_urlsafe(24)
        response.set_cookie(
            settings.guest_cookie_name,
            anon,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            path="/",
        )
    return Actor(guest_anon_id=anon, ip=client_ip(request))
