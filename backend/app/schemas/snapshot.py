"""Snapshot schemas."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ObjectType(str):
    """Object type enumeration."""

    BLOB = "blob"
    TREE = "tree"
    COMMIT = "commit"


class SnapshotCreate(BaseModel):
    """Snapshot creation schema."""

    task_id: Optional[UUID] = None
    parent_id: Optional[str] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SnapshotRead(BaseModel):
    """Snapshot read schema."""

    id: str  # SHA-256 hash
    task_id: Optional[UUID] = None
    parent_id: Optional[str] = None
    tree_hash: str
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SnapshotTree(BaseModel):
    """Snapshot tree schema."""

    snapshot: SnapshotRead
    children: List["SnapshotTree"] = Field(default_factory=list)


class SnapshotRestore(BaseModel):
    """Snapshot restore schema."""

    snapshot_id: str
    force: bool = False  # Force restore even with uncommitted changes


class ObjectRead(BaseModel):
    """Object read schema."""

    hash: str
    type: str
    size: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ObjectContent(ObjectRead):
    """Object with content."""

    content: Optional[bytes] = None  # Binary content, may be None for large objects


class SnapshotDiff(BaseModel):
    """Snapshot diff schema."""

    from_snapshot: str
    to_snapshot: str
    files_added: List[str] = Field(default_factory=list)
    files_modified: List[str] = Field(default_factory=list)
    files_deleted: List[str] = Field(default_factory=list)