"""Audit log schemas."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AuditResult(str, Enum):
    """Audit result enumeration."""

    SUCCESS = "success"
    FAILURE = "failure"


class AuditLogFilter(BaseModel):
    """Audit log filter schema."""

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    actor_user_id: Optional[UUID] = None
    action: Optional[str] = None
    resource: Optional[str] = None
    result: Optional[AuditResult] = None


class AuditLogRead(BaseModel):
    """Audit log read schema."""

    id: UUID
    timestamp: datetime
    actor_user_id: Optional[UUID] = None
    actor_username: Optional[str] = None
    actor_role: Optional[str] = None
    actor_ip_address: Optional[str] = None
    action: str
    resource: str
    resource_id: Optional[UUID] = None
    changes: Optional[Dict[str, Any]] = None
    result: str
    error_message: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    snapshot_id: Optional[str] = None

    model_config = {"from_attributes": True}


class AuditLogCreate(BaseModel):
    """Audit log creation schema (for internal use)."""

    actor_user_id: Optional[UUID] = None
    actor_username: Optional[str] = None
    actor_role: Optional[str] = None
    actor_ip_address: Optional[str] = None
    action: str
    resource: str
    resource_id: Optional[UUID] = None
    changes: Optional[Dict[str, Any]] = None
    result: AuditResult
    error_message: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    snapshot_id: Optional[str] = None


class AuditLogExport(BaseModel):
    """Audit log export schema."""

    format: str = Field(default="json", pattern="^(json|csv)$")
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    actions: Optional[List[str]] = None
    include_changes: bool = True