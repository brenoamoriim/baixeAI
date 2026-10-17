import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, in_values, uuid_pk

SUBSCRIPTION_KINDS = ("recurring", "lifetime")
SUBSCRIPTION_STATUSES = ("pending", "active", "past_due", "canceled", "expired", "refunded")
RENEWAL_MODES = ("card_auto", "manual", "one_time", "admin")
PAYMENT_PURPOSES = ("package", "plan_cycle", "lifetime")
PAYMENT_STATUSES = (
    "created",
    "pending",
    "approved",
    "rejected",
    "cancelled",
    "expired",
    "refunded",
    "charged_back",
    "in_mediation",
)


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint(in_values("kind", SUBSCRIPTION_KINDS), name="kind"),
        CheckConstraint(in_values("status", SUBSCRIPTION_STATUSES), name="status"),
        CheckConstraint(in_values("renewal_mode", RENEWAL_MODES), name="renewal_mode"),
        Index(
            "uq_subscriptions_one_live_recurring",
            "user_id",
            unique=True,
            postgresql_where=text("kind = 'recurring' AND status IN ('active', 'past_due')"),
        ),
        Index(
            "uq_subscriptions_one_active_lifetime",
            "user_id",
            unique=True,
            postgresql_where=text("kind = 'lifetime' AND status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    renewal_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_preapproval_id: Mapped[str | None] = mapped_column(String(80), unique=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    next_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id")
    )
    created_at: Mapped[datetime] = created_at_col()
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SubscriptionCycle(Base):
    __tablename__ = "subscription_cycles"
    __table_args__ = (UniqueConstraint("subscription_id", "cycle_number", name="number"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False
    )
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payments.id"), unique=True
    )
    created_at: Mapped[datetime] = created_at_col()


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(in_values("purpose", PAYMENT_PURPOSES), name="purpose"),
        CheckConstraint(in_values("status", PAYMENT_STATUSES), name="status"),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    package_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("credit_packages.id")
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id"))
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id")
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="mercadopago")
    provider_payment_id: Mapped[str | None] = mapped_column(String(80), unique=True)
    provider_preference_id: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created")
    status_detail: Mapped[str | None] = mapped_column(String(120))
    method: Mapped[str | None] = mapped_column(String(30))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = created_at_col()


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    topic: Mapped[str | None] = mapped_column(String(60))
    action: Mapped[str | None] = mapped_column(String(60))
    resource_id: Mapped[str | None] = mapped_column(String(80), index=True)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    received_at: Mapped[datetime] = created_at_col()
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
