"""Audit log model."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin
from app.models.types import JSONType


class AuditLog(Base, UUIDMixin):
    """Audit log model for tracking all actions."""

    __tablename__ = "audit_logs"

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )

    # Actor information
    actor_user_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    actor_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    actor_ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Action details
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)

    # Result
    changes: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    result: Mapped[str] = mapped_column(String(20), nullable=False)  # success, failure
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Context
    context: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("snapshots.id"), nullable=True)