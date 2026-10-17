"""Accounts and sessions. Responses avoid revealing whether an e-mail is registered."""

import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.errors import AppError, Unauthorized
from app.models import AuditEvent, EmailToken, User, UserSession
from app.security.crypto import (
    hash_password,
    keyed_hash,
    needs_rehash,
    new_token,
    token_hash,
    verify_password,
)
from app.services import email

VERIFY_TTL = timedelta(hours=48)
RESET_TTL = timedelta(hours=1)
MIN_PASSWORD = 10
MAX_PASSWORD = 128


def _validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise AppError(f"A senha precisa ter pelo menos {MIN_PASSWORD} caracteres.",
                       code="weak_password")
    if len(password) > MAX_PASSWORD:
        raise AppError("Senha longa demais.", code="weak_password")


def _audit(db: Session, action: str, user_id: uuid.UUID | None, ip: str | None, **meta) -> None:
    db.add(
        AuditEvent(
            actor_type="user" if user_id else "anonymous",
            actor_id=str(user_id) if user_id else None,
            action=action,
            target_type="user",
            target_id=str(user_id) if user_id else None,
            ip_hash=keyed_hash(ip, purpose="ip") if ip else None,
            metadata_=meta,
        )
    )


def _issue_email_token(db: Session, user: User, purpose: str, ttl: timedelta) -> str:
    token = new_token()
    db.add(
        EmailToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=token_hash(token),
            expires_at=clock.now() + ttl,
        )
    )
    return token


def _link(path: str, token: str) -> str:
    return f"{get_settings().app_base_url}{path}?token={token}"


def register(db: Session, email_address: str, password: str, ip: str | None) -> None:
    """Always 'succeeds' from the caller's view; existing e-mails get a notice instead."""
    _validate_password(password)
    email_address = email_address.strip().lower()
    with db.begin():
        existing = db.execute(select(User).where(User.email == email_address)).scalar_one_or_none()
        if existing is not None:
            _audit(db, "register_existing_email", existing.id, ip)
            pending = None
        else:
            user = User(email=email_address, password_hash=hash_password(password))
            db.add(user)
            try:
                db.flush()
            except IntegrityError:
                raise AppError("Não foi possível concluir o cadastro.", code="register_failed") from None
            pending = (user.email, _issue_email_token(db, user, "verify_email", VERIFY_TTL))
            _audit(db, "register", user.id, ip)
    if pending:
        to, token = pending
        email.send(to, "Confirme seu e-mail no BaixeAI",
                   f"Para confirmar sua conta, acesse: {_link('/verificar-email', token)}\n"
                   "O link vale por 48 horas.")
    else:
        email.send(email_address, "Tentativa de cadastro no BaixeAI",
                   "Alguém tentou criar uma conta com este e-mail, que já está cadastrado. "
                   f"Se foi você, entre ou recupere a senha em {get_settings().app_base_url}/entrar")


def _consume_token(db: Session, token: str, purpose: str) -> EmailToken:
    row = db.execute(
        select(EmailToken)
        .where(EmailToken.token_hash == token_hash(token), EmailToken.purpose == purpose)
        .with_for_update()
    ).scalar_one_or_none()
    if row is None or row.used_at is not None or row.expires_at <= clock.now():
        raise AppError("Link inválido ou expirado.", code="invalid_token")
    row.used_at = clock.now()
    return row


def verify_email(db: Session, token: str) -> None:
    with db.begin():
        row = _consume_token(db, token, "verify_email")
        user = db.get(User, row.user_id, with_for_update=True)
        if user.email_verified_at is None:
            user.email_verified_at = clock.now()


def resend_verification(db: Session, user: User) -> None:
    if user.email_verified_at is not None:
        return
    with db.begin():
        token = _issue_email_token(db, user, "verify_email", VERIFY_TTL)
    email.send(user.email, "Confirme seu e-mail no BaixeAI",
               f"Para confirmar sua conta, acesse: {_link('/verificar-email', token)}")


def login(db: Session, email_address: str, password: str, ip: str | None,
          user_agent: str | None) -> str:
    """Return a new session token (stored only as SHA-256)."""
    email_address = email_address.strip().lower()
    token = None
    with db.begin():
        user = db.execute(select(User).where(User.email == email_address)).scalar_one_or_none()
        valid = verify_password(user.password_hash if user else None, password)
        if user is None or not valid or user.status != "active":
            # Committed (not rolled back) so failed attempts stay in the audit trail.
            _audit(db, "login_failed", user.id if user else None, ip)
        else:
            token = _open_session(db, user, password, ip, user_agent)
    if token is None:
        raise Unauthorized("E-mail ou senha incorretos.", code="invalid_credentials")
    return token


def _open_session(db: Session, user: User, password: str, ip: str | None,
                  user_agent: str | None) -> str:
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    token = new_token()
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=token_hash(token),
            expires_at=clock.now() + timedelta(days=get_settings().session_ttl_days),
            ip_hash=keyed_hash(ip, purpose="ip") if ip else None,
            user_agent=(user_agent or "")[:300],
        )
    )
    _audit(db, "login", user.id, ip)
    return token


def resolve_session(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    row = db.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(
            UserSession.token_hash == token_hash(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > clock.now(),
            User.status == "active",
        )
    ).first()
    db.commit()  # end the read transaction; callers start their own
    return row[1] if row else None


def logout(db: Session, token: str | None) -> None:
    if not token:
        return
    with db.begin():
        db.execute(
            update(UserSession)
            .where(UserSession.token_hash == token_hash(token), UserSession.revoked_at.is_(None))
            .values(revoked_at=clock.now())
        )


def request_password_reset(db: Session, email_address: str, ip: str | None) -> None:
    email_address = email_address.strip().lower()
    with db.begin():
        user = db.execute(select(User).where(User.email == email_address)).scalar_one_or_none()
        token = None
        if user is not None and user.status == "active":
            token = _issue_email_token(db, user, "reset_password", RESET_TTL)
            _audit(db, "password_reset_requested", user.id, ip)
    if token:
        email.send(email_address, "Redefinição de senha do BaixeAI",
                   f"Para criar uma nova senha, acesse: {_link('/redefinir-senha', token)}\n"
                   "O link vale por 1 hora. Se não foi você, ignore este e-mail.")


def reset_password(db: Session, token: str, new_password: str, ip: str | None) -> None:
    _validate_password(new_password)
    with db.begin():
        row = _consume_token(db, token, "reset_password")
        user = db.get(User, row.user_id, with_for_update=True)
        user.password_hash = hash_password(new_password)
        # Changing the password signs out every device.
        db.execute(
            update(UserSession)
            .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=clock.now())
        )
        _audit(db, "password_reset", user.id, ip)
