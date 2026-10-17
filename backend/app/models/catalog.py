import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, in_values, uuid_pk

PLAN_KINDS = ("free", "recurring", "lifetime")
CAPABILITY_STATUSES = ("available", "planned", "unsupported")


class Plan(Base):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint(in_values("kind", PLAN_KINDS), name="kind"),
        CheckConstraint("price_cents >= 0", name="price_non_negative"),
        CheckConstraint(
            "kind <> 'recurring' OR credits_per_cycle > 0", name="recurring_has_credits"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="BRL")
    credits_per_cycle: Mapped[int | None] = mapped_column(Integer)
    is_unlimited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = created_at_col()


class ToolDefinition(Base):
    __tablename__ = "tool_definitions"
    __table_args__ = (CheckConstraint("credit_cost > 0", name="cost_positive"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    package_display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    credit_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    queue: Mapped[str] = mapped_column(String(30), nullable=False, default="default")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dev_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ToolCapability(Base):
    __tablename__ = "tool_capabilities"
    __table_args__ = (
        UniqueConstraint("tool_id", "input_format", "output_format", name="uq_tool_capabilities_io"),
        CheckConstraint(in_values("status", CAPABILITY_STATUSES), name="status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tool_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("tool_definitions.id"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    input_format: Mapped[str] = mapped_column(String(20), nullable=False)
    output_format: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    engine: Mapped[str] = mapped_column(String(40), nullable=False)
    max_input_bytes: Mapped[int | None] = mapped_column(Integer)
    options_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(String(500))
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CreditCostRule(Base):
    __tablename__ = "credit_cost_rules"
    __table_args__ = (CheckConstraint("cost > 0", name="cost_positive"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    tool_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("tool_definitions.id"), nullable=False, index=True
    )
    category: Mapped[str | None] = mapped_column(String(30))
    min_duration_seconds: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CreditPackage(Base):
    __tablename__ = "credit_packages"
    __table_args__ = (
        CheckConstraint("credits > 0", name="credits_positive"),
        CheckConstraint("price_cents >= 0", name="price_non_negative"),
        CheckConstraint("validity_days > 0", name="validity_positive"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    tool_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("tool_definitions.id"), nullable=False
    )
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    validity_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[object] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(String(300))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = created_at_col()


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(String(300))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = created_at_col()
