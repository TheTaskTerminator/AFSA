"""Orchestration layer for AFSA.

This layer handles:
- Task dispatching and scheduling
- Sandbox management and code execution
- Version control and snapshots
- Message queue integration
"""
from app.orchestration.dispatcher import TaskDispatcher, get_task_dispatcher, TaskState
from app.orchestration.sandbox import (
    SandboxPool,
    get_sandbox_pool,
    SandboxRunner,
    get_sandbox_runner,
)
from app.orchestration.version import VersionControlService, get_version_control
from app.orchestration.messaging import (
    NatsClient,
    get_nats_client,
    EventPublisher,
    get_event_publisher,
    EventSubscriber,
    get_event_subscriber,
)

__all__ = [
    # Dispatcher
    "TaskDispatcher",
    "get_task_dispatcher",
    "TaskState",
    # Sandbox
    "SandboxPool",
    "get_sandbox_pool",
    "SandboxRunner",
    "get_sandbox_runner",
    # Version Control
    "VersionControlService",
    "get_version_control",
    # Messaging
    "NatsClient",
    "get_nats_client",
    "EventPublisher",
    "get_event_publisher",
    "EventSubscriber",
    "get_event_subscriber",
]