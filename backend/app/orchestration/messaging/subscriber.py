"""Event subscriber for NATS."""
import asyncio
import logging
from typing import Callable, Optional, Set

from nats.aio.msg import Msg

from app.orchestration.messaging.nats_client import NatsConnection
from app.orchestration.messaging.publisher import Event, EventType

logger = logging.getLogger(__name__)

# Type alias for event handlers
EventHandler = Callable[[Event], None]


class EventSubscriber:
    """Subscriber for task events."""

    SUBJECT_PREFIX = "afsa.events"
    STREAM_NAME = "AFSA_EVENTS"

    def __init__(self, nats_client: NatsConnection):
        self._nats = nats_client
        self._handlers: dict[EventType, Set[EventHandler]] = {}
        self._subscriptions: list = []
        self._running = False

    async def setup_stream(self) -> None:
        """Create JetStream stream if not exists."""
        try:
            await self._nats.jetstream.add_stream(
                name=self.STREAM_NAME,
                subjects=[f"{self.SUBJECT_PREFIX}.*"],
            )
            logger.info(f"Created JetStream stream: {self.STREAM_NAME}")
        except Exception as e:
            # Stream may already exist
            if "stream name already in use" not in str(e).lower():
                logger.warning(f"Stream setup warning: {e}")

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler for an event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = set()
        self._handlers[event_type].add(handler)
        logger.debug(f"Registered handler for {event_type.value}")

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unregister a handler for an event type."""
        if event_type in self._handlers:
            self._handlers[event_type].discard(handler)

    async def start(self) -> None:
        """Start listening for events."""
        if self._running:
            return

        await self.setup_stream()

        # Subscribe to all events
        subject = f"{self.SUBJECT_PREFIX}.*"
        subscription = await self._nats.jetstream.subscribe(
            subject,
            cb=self._handle_message,
            durable="afsa-event-consumer",
        )
        self._subscriptions.append(subscription)
        self._running = True
        logger.info(f"Started event subscriber on {subject}")

    async def stop(self) -> None:
        """Stop listening for events."""
        for sub in self._subscriptions:
            await sub.unsubscribe()
        self._subscriptions.clear()
        self._running = False
        logger.info("Stopped event subscriber")

    async def _handle_message(self, msg: Msg) -> None:
        """Handle incoming message."""
        try:
            data = msg.data.decode("utf-8")
            event = Event.from_json(data)

            # Get handlers for this event type
            handlers = self._handlers.get(event.event_type, set())

            # Execute all handlers
            for handler in handlers:
                try:
                    result = handler(event)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"Handler error for {event.event_type.value}: {e}")

            # Acknowledge message
            await msg.ack()

        except Exception as e:
            logger.error(f"Failed to handle message: {e}")
            # Nak to redeliver
            await msg.nak()


# Global subscriber instance
_subscriber: Optional[EventSubscriber] = None


async def get_event_subscriber() -> EventSubscriber:
    """Get or create event subscriber."""
    global _subscriber
    if _subscriber is None:
        from app.orchestration.messaging.nats_client import get_nats_client

        nats_client = await get_nats_client()
        _subscriber = EventSubscriber(nats_client)
    return _subscriber