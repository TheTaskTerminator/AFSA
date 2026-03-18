"""Agent protocol module for inter-agent communication.

This module provides the communication protocol for agents to collaborate
on tasks, including message types, routing, and workflow coordination.
"""
from app.agents.protocol.message import (
    AgentMessage,
    AgentMessageType,
    AgentRequest,
    AgentResponse,
    BroadcastMessage,
    CollaborationContext,
    MessagePriority,
    MessageStatus,
    RequestType,
    ResponseStatus,
)
from app.agents.protocol.coordinator import (
    AgentTask,
    CollaborationResult,
    WorkflowCoordinator,
    WorkflowStage,
    WorkflowStageResult,
)
from app.agents.protocol.router import (
    AgentRouter,
    MessageRoute,
    RoutingRule,
)

__all__ = [
    # Messages
    "AgentMessage",
    "AgentMessageType",
    "AgentRequest",
    "AgentResponse",
    "BroadcastMessage",
    "CollaborationContext",
    "MessagePriority",
    "MessageStatus",
    "RequestType",
    "ResponseStatus",
    # Coordinator
    "AgentTask",
    "CollaborationResult",
    "WorkflowCoordinator",
    "WorkflowStage",
    "WorkflowStageResult",
    # Router
    "AgentRouter",
    "MessageRoute",
    "RoutingRule",
]