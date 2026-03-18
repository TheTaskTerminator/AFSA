"""Task model."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin
from app.models.types import JSONType


class Task(Base, UUIDMixin, TimestampMixin):
    """Task model for tracking agent tasks."""

    __tablename__ = "tasks"

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    description: Mapped[str] = mapped_column(Text, nullable=False)

    structured_requirements: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    constraints: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    result: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    session_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)