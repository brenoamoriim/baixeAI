"""Password hashing (Argon2id), opaque tokens and keyed hashes."""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

_hasher = PasswordHasher()  # argon2-cffi defaults to Argon2id (RFC 9106 low-memory profile)

# Used to spend comparable time when the account does not exist (mitigates user enumeration).
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def new_token() -> str:
    """Opaque random token sent to the client. Only its SHA-256 is stored."""
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _key(value: str) -> bytes:
    if not value:  # engine workers have no secrets: never sign with an empty key
        raise RuntimeError("secret not available in this process")
    return value.encode()


def keyed_hash(value: str, *, purpose: str) -> str:
    """HMAC used to store IPs and anonymous ids without keeping the raw value."""
    key = _key(get_settings().guest_id_hmac_secret)
    return hmac.new(key, f"{purpose}:{value}".encode(), hashlib.sha256).hexdigest()


def sign(message: str) -> str:
    key = _key(get_settings().signed_url_secret)
    return hmac.new(key, message.encode(), hashlib.sha256).hexdigest()


def verify_signature(message: str, signature: str) -> bool:
    return hmac.compare_digest(sign(message), signature)
