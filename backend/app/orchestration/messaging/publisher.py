"""Event publisher for NATS."""
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from app.orchestration.messaging.nats_client import NatsConnection

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Event types for task management."""

    TASK_CREATED = "task.created"
    TASK_QUEUED = "task.queued"
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_TIMEOUT = "task.timeout"

    SANDBOX_ALLOCATED = "sandbox.allocated"
    SANDBOX_RELEASED = "sandbox.released"
    SANDBOX_ERROR = "sandbox.error"

    SNAPSHOT_CREATED = "snapshot.created"
    SNAPSHOT_RESTORED = "snapshot.restored"


@dataclass
class Event:
    """Event message structure."""

    event_type: EventType
    event_id: UUID
    timestamp: datetime
    payload: dict[str, Any]
    metadata: Optional[dict[str, Any]] = None

    def to_json(self) -> str:
        """Serialize event to JSON."""
        return json.dumps({
            "event_type": self.event_type.value,
            "event_id": str(self.event_id),
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "metadata": self.metadata,
        })

    @classmethod
    def from_json(cls, data: str) -> "Event":
        """Deserialize event from JSON."""
        obj = json.loads(data)
        return cls(
            event_type=EventType(obj["event_type"]),
            event_id=UUID(obj["event_id"]),
            timestamp=datetime.fromisoformat(obj["timestamp"]),
            payload=obj["payload"],
            metadata=obj.get("metadata"),
        )


class EventPublisher:
    """Publisher for task events."""

    SUBJECT_PREFIX = "afsa.events"

    def __init__(self, nats_client: NatsConnection):
        self._nats = nats_client

    async def publish(
        self,
        event_type: EventType,
        payload: dict[str, Any],
        metadata: Optional[dict[str, Any]] = None,
    ) -> UUID:
        """Publish an event."""
        event = Event(
            event_type=event_type,
            event_id=uuid4(),
            timestamp=datetime.utcnow(),
            payload=payload,
            metadata=metadata,
        )

        subject = f"{self.SUBJECT_PREFIX}.{event_type.value}"
        message = event.to_json().encode("utf-8")

        try:
            await self._nats.jetstream.publish(subject, message)
            logger.debug(f"Published event {event.event_id} to {subject}")
            return event.event_id
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            raise

    async def publish_task_event(
        self,
        event_type: EventType,
        task_id: UUID,
        **kwargs: Any,
    ) -> UUID:
        """Convenience method for task events."""
        payload = {"task_id": str(task_id), **kwargs}
        return await self.publish(event_type, payload)

    async def publish_sandbox_event(
        self,
        event_type: EventType,
        sandbox_id: str,
        **kwargs: Any,
    ) -> UUID:
        """Convenience method for sandbox events."""
        payload = {"sandbox_id": sandbox_id, **kwargs}
        return await self.publish(event_type, payload)


# Global publisher instance
_publisher: Optional[EventPublisher] = None


async def get_event_publisher() -> EventPublisher:
    """Get or create event publisher."""
    global _publisher
    if _publisher is None:
        from app.orchestration.messaging.nats_client import get_nats_client

        nats_client = await get_nats_client()
        _publisher = EventPublisher(nats_client)
    return _publisher