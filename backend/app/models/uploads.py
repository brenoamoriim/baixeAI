import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col, in_values, uuid_pk

UPLOAD_STATUSES = ("probing", "ready", "rejected")


class Upload(Base):
    """A user file waiting to be processed. Validated (probed) BEFORE any credit is charged."""

    __tablename__ = "uploads"
    __table_args__ = (
        CheckConstraint(in_values("status", UPLOAD_STATUSES), name="status"),
        CheckConstraint("(owner_user_id IS NOT NULL) <> (owner_anon_hash IS NOT NULL)", name="one_owner"),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        Index("ix_uploads_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    owner_anon_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False)
    original_name: Mapped[str] = mapped_column(String(200), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="probing")
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(60))
    error_message: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = created_at_col()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
