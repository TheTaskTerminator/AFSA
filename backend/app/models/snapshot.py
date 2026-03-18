"""Snapshot models for Git-like version control."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.types import JSONType


class Snapshot(Base):
    """Snapshot model for version control (like Git commit)."""

    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA-256 hash
    task_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=True
    )
    parent_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("snapshots.id"), nullable=True)
    tree_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    snap_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONType, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    children: Mapped[list["Snapshot"]] = relationship(
        "Snapshot", back_populates="parent", remote_side=[id]
    )
    parent: Mapped[Optional["Snapshot"]] = relationship(
        "Snapshot", back_populates="children", remote_side=[parent_id]
    )


class Object(Base):
    """Object model for content-addressable storage (like Git object)."""

    __tablename__ = "objects"

    hash: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA-256 hash
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # blob, tree, commit
    content: Mapped[bytes] = mapped_column(nullable=False)  # Binary content
    size: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)