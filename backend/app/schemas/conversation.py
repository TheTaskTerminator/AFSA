"""Conversation schemas."""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message role enumeration."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class SessionStatus(str, Enum):
    """Session status enumeration."""

    ACTIVE = "active"
    CLOSED = "closed"
    EXPIRED = "expired"


class MessageCreate(BaseModel):
    """Message creation schema."""

    content: str = Field(..., min_length=1, max_length=10000)
    metadata: Optional[Dict[str, Any]] = None


class MessageRead(BaseModel):
    """Message read schema."""

    id: UUID
    session_id: UUID
    role: MessageRole
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionCreate(BaseModel):
    """Session creation schema."""

    user_id: Optional[UUID] = None
    expires_in_seconds: Optional[int] = None  # Session TTL


class SessionRead(BaseModel):
    """Session read schema."""

    id: UUID
    user_id: Optional[UUID] = None
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    messages: List[MessageRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SessionSummary(BaseModel):
    """Session summary schema (without messages)."""

    id: UUID
    user_id: Optional[UUID] = None
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    message_count: int = 0

    model_config = {"from_attributes": True}