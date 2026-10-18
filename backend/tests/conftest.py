"""Test setup: real PostgreSQL (separate `baixeai_test` database) and real Redis (db 15).

Environment must be set before any `app` import, because settings and the engine are created
at import time.
"""

import os
import uuid

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://baixeai:baixeai_dev_only@db:5432/baixeai_test"
)
os.environ["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://redis:6379/0").rsplit("/", 1)[0] + "/15"
os.environ["APP_ENV"] = "test"
os.environ["EMAIL_PROVIDER"] = "memory"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["COOKIE_SECURE"] = "false"
os.environ["STORAGE_LOCAL_ROOT"] = "/tmp/baixeai-test-storage"  # noqa: S108

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import cli  # noqa: E402
from app.core import clock  # noqa: E402
from app.core.db import SessionLocal, engine  # noqa: E402
from app.models import Base, User  # noqa: E402
from app.security.crypto import hash_password  # noqa: E402
from app.security.rate_limit import get_redis  # noqa: E402
from app.services import email  # noqa: E402

PASSWORD = "senha-forte-123"
_PASSWORD_HASH = hash_password(PASSWORD)


NO_DB = os.environ.get("TESTS_NO_DB") == "1"  # worker-download has no database by design


@pytest.fixture(scope="session", autouse=True)
def _schema():
    if NO_DB:
        yield
        return
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = os.environ["DATABASE_URL"]
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_state():
    if NO_DB:
        yield
        return
    tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        # Test-only: replica role skips the append-only triggers so tables can be reset.
        conn.execute(text("SET session_replication_role = replica"))
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        conn.execute(text("SET session_replication_role = DEFAULT"))
    cli.seed()
    get_redis().flushdb()
    email.outbox.clear()
    clock.freeze(None)
    yield
    clock.freeze(None)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def make_user(email_address: str | None = None, *, verified: bool = True, role: str = "user") -> User:
    with SessionLocal() as session, session.begin():
        user = User(
            email=email_address or f"user-{uuid.uuid4().hex[:8]}@exemplo.com",
            password_hash=_PASSWORD_HASH,
            role=role,
            email_verified_at=clock.now() if verified else None,
        )
        session.add(user)
    return user


class ApiClient(TestClient):
    """TestClient that fetches the CSRF cookie and echoes it on every unsafe request."""

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        token = self.get("/api/v1/auth/csrf").json()["csrf_token"]
        self.headers["X-CSRF-Token"] = token

    def login(self, email_address: str, password: str = PASSWORD):
        response = self.post("/api/v1/auth/login", json={"email": email_address, "password": password})
        assert response.status_code == 200, response.text
        return response

    def create_echo(self, key: str | None = None, **options):
        return self.post(
            "/api/v1/jobs",
            json={"tool_id": "echo", "input_format": "text", "output_format": "txt",
                  "options": {"text": "olá", **options}},
            headers={"Idempotency-Key": key or uuid.uuid4().hex},
        )


@pytest.fixture
def client():
    from app.main import app

    with ApiClient(app) as c:
        yield c


@pytest.fixture
def new_client():
    """Factory for independent browsers (separate cookie jars)."""
    from app.main import app

    clients = []

    def factory() -> ApiClient:
        c = ApiClient(app)
        clients.append(c)
        return c

    yield factory
    for c in clients:
        c.close()
