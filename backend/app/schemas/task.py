"""Task schemas."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    """Task type enumeration."""

    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    TEST = "test"
    DOC = "doc"


class TaskPriority(str, Enum):
    """Task priority enumeration."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(str, Enum):
    """Task status enumeration."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StructuredRequirement(BaseModel):
    """Structured requirement schema."""

    field: str
    type: str  # select, date_range, text, number, etc.
    options: Optional[List[str]] = None
    default: Optional[Any] = None


class TaskConstraints(BaseModel):
    """Task constraints schema."""

    target_zone: str = Field(default="mutable")  # mutable, immutable
    affected_modules: List[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=300)


class TaskBase(BaseModel):
    """Base task schema."""

    type: TaskType
    priority: TaskPriority = TaskPriority.MEDIUM
    description: str = Field(..., min_length=10)


class TaskCreate(TaskBase):
    """Task creation schema."""

    structured_requirements: Optional[List[StructuredRequirement]] = None
    constraints: Optional[TaskConstraints] = None
    session_id: Optional[UUID] = None


class TaskUpdate(BaseModel):
    """Task update schema."""

    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class TaskResult(BaseModel):
    """Task result schema."""

    success: bool
    output: Optional[str] = None
    files_changed: List[str] = Field(default_factory=list)
    snapshot_id: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


class TaskRead(TaskBase):
    """Task read schema."""

    id: UUID
    status: TaskStatus
    structured_requirements: Optional[List[StructuredRequirement]] = None
    constraints: Optional[TaskConstraints] = None
    result: Optional[TaskResult] = None
    error_message: Optional[str] = None
    user_id: Optional[UUID] = None
    session_id: Optional[UUID] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    timeout_seconds: int

    model_config = {"from_attributes": True}


class TaskProgress(BaseModel):
    """Task progress schema for WebSocket updates."""

    task_id: UUID
    status: TaskStatus
    progress: int = Field(..., ge=0, le=100)
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)