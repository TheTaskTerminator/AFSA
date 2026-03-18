"""Agent message types for inter-agent communication.

This module defines the message protocol for agents to communicate
with each other in a structured and type-safe manner.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from app.agents.base import AgentType, TaskCard


class AgentMessageType(str, Enum):
    """Types of messages exchanged between agents."""

    # Request-response pattern
    REQUEST = "request"
    RESPONSE = "response"

    # Notification pattern (no response expected)
    NOTIFICATION = "notification"

    # Broadcast pattern (one-to-many)
    BROADCAST = "broadcast"

    # Collaboration pattern
    COLLABORATION_REQUEST = "collaboration_request"
    COLLABORATION_RESPONSE = "collaboration_response"
    COLLABORATION_UPDATE = "collaboration_update"


class RequestType(str, Enum):
    """Types of requests agents can make to each other."""

    # Architect requests
    ARCHITECT_REVIEW = "architect.review"
    ARCHITECT_VALIDATE = "architect.validate"
    ARCHITECT_ANALYZE = "architect.analyze"

    # Backend requests
    BACKEND_GENERATE = "backend.generate"
    BACKEND_MODIFY = "backend.modify"
    BACKEND_VALIDATE = "backend.validate"

    # Frontend requests
    FRONTEND_GENERATE = "frontend.generate"
    FRONTEND_MODIFY = "frontend.modify"
    FRONTEND_VALIDATE = "frontend.validate"

    # Data requests
    DATA_MIGRATION = "data.migration"
    DATA_SCHEMA = "data.schema"
    DATA_VALIDATE = "data.validate"

    # PM requests
    PM_CLARIFY = "pm.clarify"
    PM_DISPATCH = "pm.dispatch"
    PM_REPORT = "pm.report"


class ResponseStatus(str, Enum):
    """Status of agent responses."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    PENDING = "pending"
    REJECTED = "rejected"
    NEEDS_CLARIFICATION = "needs_clarification"


class MessagePriority(str, Enum):
    """Priority levels for agent messages."""

    CRITICAL = "critical"  # Requires immediate attention
    HIGH = "high"  # Important but not critical
    NORMAL = "normal"  # Default priority
    LOW = "low"  # Can be processed later


class MessageStatus(str, Enum):
    """Status of messages in the system."""

    PENDING = "pending"
    DELIVERED = "delivered"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class CollaborationContext:
    """Shared context for agent collaboration.

    This context is passed along during multi-agent workflows
    to maintain state and share information.
    """

    workflow_id: str
    session_id: str
    original_request: str
    task_card: Optional[TaskCard] = None
    shared_data: Dict[str, Any] = field(default_factory=dict)
    agent_results: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def update(self, key: str, value: Any) -> None:
        """Update shared data."""
        self.shared_data[key] = value
        self.updated_at = datetime.utcnow()

    def get_agent_result(self, agent_type: AgentType) -> Optional[Any]:
        """Get result from a specific agent."""
        return self.agent_results.get(agent_type.value)

    def set_agent_result(self, agent_type: AgentType, result: Any) -> None:
        """Set result from a specific agent."""
        self.agent_results[agent_type.value] = result
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "workflow_id": self.workflow_id,
            "session_id": self.session_id,
            "original_request": self.original_request,
            "task_card": self.task_card.__dict__ if self.task_card else None,
            "shared_data": self.shared_data,
            "agent_results": self.agent_results,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CollaborationContext":
        """Create from dictionary."""
        task_card = None
        if data.get("task_card"):
            task_card = TaskCard(**data["task_card"])

        return cls(
            workflow_id=data["workflow_id"],
            session_id=data["session_id"],
            original_request=data["original_request"],
            task_card=task_card,
            shared_data=data.get("shared_data", {}),
            agent_results=data.get("agent_results", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


@dataclass
class AgentMessage:
    """Base message structure for agent communication.

    All messages between agents follow this structure to ensure
    consistent communication patterns.
    """

    message_id: str
    message_type: AgentMessageType
    sender: AgentType
    receiver: AgentType
    timestamp: datetime
    priority: MessagePriority = MessagePriority.NORMAL
    status: MessageStatus = MessageStatus.PENDING
    correlation_id: Optional[str] = None  # For request-response correlation
    context: Optional[CollaborationContext] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Generate message ID if not provided."""
        if not self.message_id:
            self.message_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "sender": self.sender.value,
            "receiver": self.receiver.value,
            "timestamp": self.timestamp.isoformat(),
            "priority": self.priority.value,
            "status": self.status.value,
            "correlation_id": self.correlation_id,
            "context": self.context.to_dict() if self.context else None,
            "payload": self.payload,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Create from dictionary."""
        context = None
        if data.get("context"):
            context = CollaborationContext.from_dict(data["context"])

        return cls(
            message_id=data["message_id"],
            message_type=AgentMessageType(data["message_type"]),
            sender=AgentType(data["sender"]),
            receiver=AgentType(data["receiver"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            priority=MessagePriority(data.get("priority", "normal")),
            status=MessageStatus(data.get("status", "pending")),
            correlation_id=data.get("correlation_id"),
            context=context,
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass
class AgentRequest(AgentMessage):
    """Request message from one agent to another.

    Used when an agent needs another agent to perform an action
    and expects a response.
    """

    request_type: RequestType = RequestType.PM_DISPATCH
    timeout_seconds: int = 300
    requires_confirmation: bool = False

    def __post_init__(self) -> None:
        """Set message type to REQUEST."""
        self.message_type = AgentMessageType.REQUEST
        if not self.message_id:
            self.message_id = str(uuid.uuid4())

    @classmethod
    def create(
        cls,
        sender: AgentType,
        receiver: AgentType,
        request_type: RequestType,
        payload: Dict[str, Any],
        context: Optional[CollaborationContext] = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        timeout_seconds: int = 300,
    ) -> "AgentRequest":
        """Factory method to create a request."""
        return cls(
            message_id=str(uuid.uuid4()),
            message_type=AgentMessageType.REQUEST,
            sender=sender,
            receiver=receiver,
            timestamp=datetime.utcnow(),
            priority=priority,
            context=context,
            payload=payload,
            request_type=request_type,
            timeout_seconds=timeout_seconds,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        base = super().to_dict()
        base.update({
            "request_type": self.request_type.value,
            "timeout_seconds": self.timeout_seconds,
            "requires_confirmation": self.requires_confirmation,
        })
        return base

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentRequest":
        """Create from dictionary."""
        context = None
        if data.get("context"):
            context = CollaborationContext.from_dict(data["context"])

        return cls(
            message_id=data["message_id"],
            message_type=AgentMessageType(data["message_type"]),
            sender=AgentType(data["sender"]),
            receiver=AgentType(data["receiver"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            priority=MessagePriority(data.get("priority", "normal")),
            status=MessageStatus(data.get("status", "pending")),
            correlation_id=data.get("correlation_id"),
            context=context,
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
            request_type=RequestType(data.get("request_type", "pm.dispatch")),
            timeout_seconds=data.get("timeout_seconds", 300),
            requires_confirmation=data.get("requires_confirmation", False),
        )


@dataclass
class AgentResponse(AgentMessage):
    """Response message from an agent to a request.

    Used to return results or status from a request.
    """

    response_status: ResponseStatus = ResponseStatus.SUCCESS
    result: Optional[Any] = None
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Set message type to RESPONSE."""
        self.message_type = AgentMessageType.RESPONSE
        if not self.message_id:
            self.message_id = str(uuid.uuid4())

    @classmethod
    def create(
        cls,
        request: AgentRequest,
        response_status: ResponseStatus,
        result: Optional[Any] = None,
        error_message: Optional[str] = None,
        warnings: Optional[List[str]] = None,
    ) -> "AgentResponse":
        """Factory method to create a response to a request."""
        return cls(
            message_id=str(uuid.uuid4()),
            message_type=AgentMessageType.RESPONSE,
            sender=request.receiver,
            receiver=request.sender,
            timestamp=datetime.utcnow(),
            priority=request.priority,
            correlation_id=request.message_id,
            context=request.context,
            payload={},
            response_status=response_status,
            result=result,
            error_message=error_message,
            warnings=warnings or [],
        )

    @classmethod
    def success(
        cls,
        request: AgentRequest,
        result: Any,
        warnings: Optional[List[str]] = None,
    ) -> "AgentResponse":
        """Create a success response."""
        return cls.create(
            request=request,
            response_status=ResponseStatus.SUCCESS,
            result=result,
            warnings=warnings,
        )

    @classmethod
    def failure(
        cls,
        request: AgentRequest,
        error_message: str,
        partial_result: Optional[Any] = None,
    ) -> "AgentResponse":
        """Create a failure response."""
        status = ResponseStatus.FAILURE
        if partial_result is not None:
            status = ResponseStatus.PARTIAL

        return cls.create(
            request=request,
            response_status=status,
            result=partial_result,
            error_message=error_message,
        )

    @classmethod
    def needs_clarification(
        cls,
        request: AgentRequest,
        questions: List[str],
    ) -> "AgentResponse":
        """Create a response indicating clarification is needed."""
        return cls.create(
            request=request,
            response_status=ResponseStatus.NEEDS_CLARIFICATION,
            result={"questions": questions},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        base = super().to_dict()
        base.update({
            "response_status": self.response_status.value,
            "result": self.result,
            "error_message": self.error_message,
            "warnings": self.warnings,
        })
        return base

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentResponse":
        """Create from dictionary."""
        context = None
        if data.get("context"):
            context = CollaborationContext.from_dict(data["context"])

        return cls(
            message_id=data["message_id"],
            message_type=AgentMessageType(data["message_type"]),
            sender=AgentType(data["sender"]),
            receiver=AgentType(data["receiver"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            priority=MessagePriority(data.get("priority", "normal")),
            status=MessageStatus(data.get("status", "pending")),
            correlation_id=data.get("correlation_id"),
            context=context,
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
            response_status=ResponseStatus(data.get("response_status", "success")),
            result=data.get("result"),
            error_message=data.get("error_message"),
            warnings=data.get("warnings", []),
        )


@dataclass
class BroadcastMessage(AgentMessage):
    """Broadcast message from one agent to multiple agents.

    Used for notifications that need to reach all relevant agents.
    """

    target_agents: List[AgentType] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Set message type to BROADCAST."""
        self.message_type = AgentMessageType.BROADCAST
        if not self.message_id:
            self.message_id = str(uuid.uuid4())

    @classmethod
    def create(
        cls,
        sender: AgentType,
        target_agents: List[AgentType],
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> "BroadcastMessage":
        """Factory method to create a broadcast message."""
        return cls(
            message_id=str(uuid.uuid4()),
            message_type=AgentMessageType.BROADCAST,
            sender=sender,
            receiver=AgentType.PM,  # Default, actual targets in target_agents
            timestamp=datetime.utcnow(),
            priority=priority,
            payload=payload,
            target_agents=target_agents,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        base = super().to_dict()
        base["target_agents"] = [a.value for a in self.target_agents]
        return base

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BroadcastMessage":
        """Create from dictionary."""
        context = None
        if data.get("context"):
            context = CollaborationContext.from_dict(data["context"])

        return cls(
            message_id=data["message_id"],
            message_type=AgentMessageType(data["message_type"]),
            sender=AgentType(data["sender"]),
            receiver=AgentType(data["receiver"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            priority=MessagePriority(data.get("priority", "normal")),
            status=MessageStatus(data.get("status", "pending")),
            correlation_id=data.get("correlation_id"),
            context=context,
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {}),
            target_agents=[AgentType(a) for a in data.get("target_agents", [])],
        )