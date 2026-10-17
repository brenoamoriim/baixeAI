import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, in_values, uuid_pk

BUCKET_KINDS = ("daily", "plan", "package", "compensation")
BUCKET_STATUSES = ("active", "expired", "revoked")
RESERVATION_STATUSES = ("reserved", "committed", "released")
LEDGER_TYPES = ("grant", "reserve", "commit", "release", "expire", "revoke", "adjust")
GUEST_STATUSES = ("available", "reserved", "consumed")


class CreditBucket(Base):
    __tablename__ = "credit_buckets"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "period_key", name="period"),
        CheckConstraint(in_values("kind", BUCKET_KINDS), name="kind"),
        CheckConstraint(in_values("status", BUCKET_STATUSES), name="status"),
        CheckConstraint("granted > 0", name="granted_positive"),
        CheckConstraint("available >= 0", name="available_non_negative"),
        CheckConstraint("reserved >= 0", name="reserved_non_negative"),
        CheckConstraint("available + reserved <= granted", name="within_granted"),
        CheckConstraint("kind <> 'package' OR tool_id IS NOT NULL", name="package_has_tool"),
        CheckConstraint("expires_at > valid_from", name="valid_window"),
        Index(
            "ix_credit_buckets_consumable",
            "user_id",
            "expires_at",
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    tool_id: Mapped[str | None] = mapped_column(String(40), ForeignKey("tool_definitions.id"))
    source_payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id")
    )
    subscription_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscription_cycles.id")
    )
    period_key: Mapped[str] = mapped_column(String(80), nullable=False)
    granted: Mapped[int] = mapped_column(Integer, nullable=False)
    available: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = created_at_col()


class CreditReservation(Base):
    __tablename__ = "credit_reservations"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="idempotency"),
        CheckConstraint(in_values("status", RESERVATION_STATUSES), name="status"),
        CheckConstraint("amount > 0", name="amount_positive"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processing_jobs.id"), unique=True, nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="reserved")
    created_at: Mapped[datetime] = created_at_col()
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CreditReservationItem(Base):
    __tablename__ = "credit_reservation_items"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    reservation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credit_reservations.id"), primary_key=True
    )
    bucket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credit_buckets.id"), primary_key=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)


class CreditLedger(Base):
    """Append-only. UPDATE/DELETE are blocked by a database trigger (see migration)."""

    __tablename__ = "credit_ledger"
    __table_args__ = (CheckConstraint(in_values("entry_type", LEDGER_TYPES), name="entry_type"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    bucket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credit_buckets.id"), nullable=False, index=True
    )
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False)
    delta_available: Mapped[int] = mapped_column(Integer, nullable=False)
    delta_reserved: Mapped[int] = mapped_column(Integer, nullable=False)
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credit_reservations.id")
    )
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id")
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processing_jobs.id")
    )
    actor: Mapped[str] = mapped_column(String(60), nullable=False, default="system")
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = created_at_col()


class GuestAllowance(Base):
    __tablename__ = "guest_allowances"
    __table_args__ = (
        CheckConstraint(in_values("status", GUEST_STATUSES), name="status"),
        Index("ix_guest_allowances_ip_created", "ip_hash", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    anon_id_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = created_at_col()
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
