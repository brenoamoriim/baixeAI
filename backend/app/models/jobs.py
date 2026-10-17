import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, in_values, uuid_pk

JOB_STATUSES = ("queued", "processing", "completed", "failed", "expired")
ERROR_CLASSES = ("user_input", "system", "timeout")
CHARGED_FROM = ("credits", "lifetime", "guest")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        CheckConstraint(in_values("status", JOB_STATUSES), name="status"),
        CheckConstraint(
            "error_class IS NULL OR " + in_values("error_class", ERROR_CLASSES), name="error_class"
        ),
        CheckConstraint(in_values("charged_from", CHARGED_FROM), name="charged_from"),
        CheckConstraint(
            "(user_id IS NOT NULL) <> (guest_allowance_id IS NOT NULL)", name="one_owner"
        ),
        Index(
            "uq_processing_jobs_user_idempotency",
            "user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
        Index(
            "uq_processing_jobs_guest_idempotency",
            "guest_allowance_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("guest_allowance_id IS NOT NULL"),
        ),
        Index("ix_processing_jobs_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    guest_allowance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guest_allowances.id")
    )
    tool_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("tool_definitions.id"), nullable=False
    )
    capability_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tool_capabilities.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    charged_from: Mapped[str] = mapped_column(String(20), nullable=False)
    credit_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    input_meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    options: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    input_key: Mapped[str | None] = mapped_column(String(300))
    output_key: Mapped[str | None] = mapped_column(String(300))
    output_filename: Mapped[str | None] = mapped_column(String(200))
    output_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_class: Mapped[str | None] = mapped_column(String(20))
    queue: Mapped[str] = mapped_column(String(30), nullable=False)
    task_id: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = created_at_col()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsageRecord(Base):
    __tablename__ = "usage_records"
    __table_args__ = (
        CheckConstraint(in_values("charged_from", CHARGED_FROM), name="charged_from"),
        Index("ix_usage_records_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    guest_allowance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guest_allowances.id")
    )
    tool_id: Mapped[str] = mapped_column(String(40), nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processing_jobs.id"), unique=True, nullable=False
    )
    credits_charged: Mapped[int] = mapped_column(Integer, nullable=False)
    charged_from: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = created_at_col()


class AuditEvent(Base):
    """Append-only (trigger in migration)."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[str | None] = mapped_column(String(80))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = created_at_col()
