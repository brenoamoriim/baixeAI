import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, in_values, uuid_pk

INSPECTION_STATUSES = ("probing", "ready", "rejected")


class UrlInspection(Base):
    """A video URL inspected by the extractor (real options) BEFORE any credit is charged."""

    __tablename__ = "url_inspections"
    __table_args__ = (
        CheckConstraint(in_values("status", INSPECTION_STATUSES), name="status"),
        CheckConstraint("(owner_user_id IS NOT NULL) <> (owner_anon_hash IS NOT NULL)", name="one_owner"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    owner_anon_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="probing")
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = created_at_col()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
