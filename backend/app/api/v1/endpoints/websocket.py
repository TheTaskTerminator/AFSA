"""WebSocket endpoints for real-time task updates."""
import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WSMessageType(str, Enum):
    """WebSocket message types."""

    # Client -> Server
    SUBSCRIBE_TASK = "subscribe_task"
    UNSUBSCRIBE_TASK = "unsubscribe_task"
    SUBSCRIBE_ALL = "subscribe_all"
    PING = "ping"

    # Server -> Client
    TASK_PROGRESS = "task_progress"
    TASK_STATUS = "task_status"
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    PONG = "pong"
    ERROR = "error"


@dataclass
class WSMessage:
    """WebSocket message structure."""

    type: WSMessageType
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_json(self) -> str:
        """Serialize message to JSON."""
        return json.dumps({
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        })

    @classmethod
    def from_json(cls, data: str) -> "WSMessage":
        """Deserialize message from JSON."""
        obj = json.loads(data)
        return cls(
            type=WSMessageType(obj["type"]),
            data=obj.get("data", {}),
            timestamp=datetime.fromisoformat(obj["timestamp"])
            if "timestamp" in obj
            else datetime.utcnow(),
        )


class ConnectionManager:
    """Manages WebSocket connections and subscriptions."""

    def __init__(self):
        # Active connections: websocket -> connection info
        self._connections: dict[WebSocket, dict] = {}
        # Task subscriptions: task_id -> set of websockets
        self._task_subscribers: dict[UUID, set[WebSocket]] = {}
        # Global subscribers (receive all events)
        self._global_subscribers: set[WebSocket] = set()
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self._connections[websocket] = {
                "connected_at": datetime.utcnow(),
                "subscriptions": set(),
            }
        logger.info(f"WebSocket connected: {id(websocket)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            # Remove from connections
            if websocket in self._connections:
                # Clean up task subscriptions
                for task_id in self._connections[websocket].get("subscriptions", set()):
                    if task_id in self._task_subscribers:
                        self._task_subscribers[task_id].discard(websocket)
                        if not self._task_subscribers[task_id]:
                            del self._task_subscribers[task_id]

                # Remove from global subscribers
                self._global_subscribers.discard(websocket)

                # Remove connection
                del self._connections[websocket]

        logger.info(f"WebSocket disconnected: {id(websocket)}")

    async def subscribe_task(self, websocket: WebSocket, task_id: UUID) -> None:
        """Subscribe a connection to task updates."""
        async with self._lock:
            if websocket not in self._connections:
                return

            # Add to task subscribers
            if task_id not in self._task_subscribers:
                self._task_subscribers[task_id] = set()
            self._task_subscribers[task_id].add(websocket)

            # Track subscription in connection
            self._connections[websocket]["subscriptions"].add(task_id)

        logger.debug(f"WebSocket {id(websocket)} subscribed to task {task_id}")

    async def unsubscribe_task(self, websocket: WebSocket, task_id: UUID) -> None:
        """Unsubscribe a connection from task updates."""
        async with self._lock:
            if task_id in self._task_subscribers:
                self._task_subscribers[task_id].discard(websocket)
                if not self._task_subscribers[task_id]:
                    del self._task_subscribers[task_id]

            if websocket in self._connections:
                self._connections[websocket]["subscriptions"].discard(task_id)

        logger.debug(f"WebSocket {id(websocket)} unsubscribed from task {task_id}")

    async def subscribe_all(self, websocket: WebSocket) -> None:
        """Subscribe a connection to all task updates."""
        async with self._lock:
            self._global_subscribers.add(websocket)
            if websocket in self._connections:
                self._connections[websocket]["is_global"] = True

        logger.debug(f"WebSocket {id(websocket)} subscribed to all tasks")

    async def broadcast_task_progress(
        self,
        task_id: UUID,
        progress_percent: int,
        message: str = "",
        status: Optional[str] = None,
    ) -> None:
        """Broadcast task progress update to subscribers."""
        ws_message = WSMessage(
            type=WSMessageType.TASK_PROGRESS,
            data={
                "task_id": str(task_id),
                "progress_percent": progress_percent,
                "message": message,
                "status": status,
            },
        )
        await self._broadcast_to_subscribers(task_id, ws_message)

    async def broadcast_task_status(
        self,
        task_id: UUID,
        status: str,
        message: str = "",
    ) -> None:
        """Broadcast task status update to subscribers."""
        ws_message = WSMessage(
            type=WSMessageType.TASK_STATUS,
            data={
                "task_id": str(task_id),
                "status": status,
                "message": message,
            },
        )
        await self._broadcast_to_subscribers(task_id, ws_message)

    async def broadcast_task_created(self, task_id: UUID, task_data: dict[str, Any]) -> None:
        """Broadcast task creation to global subscribers."""
        ws_message = WSMessage(
            type=WSMessageType.TASK_CREATED,
            data={
                "task_id": str(task_id),
                **task_data,
            },
        )
        await self._broadcast_global(ws_message)

    async def broadcast_task_completed(
        self,
        task_id: UUID,
        result: Optional[dict[str, Any]] = None,
    ) -> None:
        """Broadcast task completion to subscribers."""
        ws_message = WSMessage(
            type=WSMessageType.TASK_COMPLETED,
            data={
                "task_id": str(task_id),
                "result": result,
            },
        )
        await self._broadcast_to_subscribers(task_id, ws_message)

    async def broadcast_task_failed(
        self,
        task_id: UUID,
        error: str,
    ) -> None:
        """Broadcast task failure to subscribers."""
        ws_message = WSMessage(
            type=WSMessageType.TASK_FAILED,
            data={
                "task_id": str(task_id),
                "error": error,
            },
        )
        await self._broadcast_to_subscribers(task_id, ws_message)

    async def send_error(self, websocket: WebSocket, error_message: str) -> None:
        """Send error message to a specific connection."""
        ws_message = WSMessage(
            type=WSMessageType.ERROR,
            data={"error": error_message},
        )
        try:
            await websocket.send_text(ws_message.to_json())
        except Exception as e:
            logger.error(f"Failed to send error: {e}")

    async def send_pong(self, websocket: WebSocket) -> None:
        """Send pong response to a specific connection."""
        ws_message = WSMessage(
            type=WSMessageType.PONG,
            data={},
        )
        try:
            await websocket.send_text(ws_message.to_json())
        except Exception as e:
            logger.error(f"Failed to send pong: {e}")

    async def _broadcast_to_subscribers(self, task_id: UUID, message: WSMessage) -> None:
        """Broadcast message to task subscribers and global subscribers."""
        message_json = message.to_json()

        # Collect recipients
        recipients: set[WebSocket] = set()

        async with self._lock:
            # Task-specific subscribers
            if task_id in self._task_subscribers:
                recipients.update(self._task_subscribers[task_id])

            # Global subscribers
            recipients.update(self._global_subscribers)

        # Send to all recipients
        disconnected = []
        for websocket in recipients:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.append(websocket)

        # Clean up disconnected
        for ws in disconnected:
            await self.disconnect(ws)

    async def _broadcast_global(self, message: WSMessage) -> None:
        """Broadcast message to global subscribers only."""
        message_json = message.to_json()

        async with self._lock:
            recipients = set(self._global_subscribers)

        disconnected = []
        for websocket in recipients:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.append(websocket)

        for ws in disconnected:
            await self.disconnect(ws)

    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self._connections)

    def get_subscriber_count(self, task_id: UUID) -> int:
        """Get the number of subscribers for a task."""
        return len(self._task_subscribers.get(task_id, set()))


# Global connection manager instance
_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get or create the global connection manager."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager


# WebSocket Router
router = APIRouter()


@router.websocket("")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time task updates.

    Protocol:
    - Client sends JSON messages with 'type' and optional 'data' fields
    - Server responds with JSON messages containing 'type', 'data', and 'timestamp'

    Message Types (Client -> Server):
    - subscribe_task: Subscribe to a specific task's updates
    - unsubscribe_task: Unsubscribe from a task's updates
    - subscribe_all: Subscribe to all task events
    - ping: Health check

    Message Types (Server -> Client):
    - task_progress: Progress update for a task
    - task_status: Status change for a task
    - task_created: New task created
    - task_completed: Task completed successfully
    - task_failed: Task failed with error
    - pong: Response to ping
    - error: Error message

    Example:
        # Subscribe to a task
        {"type": "subscribe_task", "data": {"task_id": "uuid-here"}}

        # Receive progress
        {"type": "task_progress", "data": {"task_id": "...", "progress_percent": 50}}
    """
    manager = get_connection_manager()
    await manager.connect(websocket)

    try:
        while True:
            # Receive message
            data = await websocket.receive_text()

            # Parse message
            try:
                message = json.loads(data)
                msg_type = message.get("type", "")
                msg_data = message.get("data", {})
            except json.JSONDecodeError:
                await manager.send_error(websocket, "Invalid JSON format")
                continue

            # Handle message by type
            try:
                if msg_type == WSMessageType.SUBSCRIBE_TASK.value:
                    task_id_str = msg_data.get("task_id")
                    if not task_id_str:
                        await manager.send_error(websocket, "Missing task_id")
                        continue

                    try:
                        task_id = UUID(task_id_str)
                        await manager.subscribe_task(websocket, task_id)
                        # Send confirmation
                        confirm = WSMessage(
                            type=WSMessageType.TASK_STATUS,
                            data={
                                "task_id": str(task_id),
                                "status": "subscribed",
                                "message": f"Successfully subscribed to task {task_id}",
                            },
                        )
                        await websocket.send_text(confirm.to_json())
                    except ValueError:
                        await manager.send_error(websocket, "Invalid task_id format")

                elif msg_type == WSMessageType.UNSUBSCRIBE_TASK.value:
                    task_id_str = msg_data.get("task_id")
                    if not task_id_str:
                        await manager.send_error(websocket, "Missing task_id")
                        continue

                    try:
                        task_id = UUID(task_id_str)
                        await manager.unsubscribe_task(websocket, task_id)
                    except ValueError:
                        await manager.send_error(websocket, "Invalid task_id format")

                elif msg_type == WSMessageType.SUBSCRIBE_ALL.value:
                    await manager.subscribe_all(websocket)
                    confirm = WSMessage(
                        type=WSMessageType.TASK_STATUS,
                        data={
                            "status": "subscribed_all",
                            "message": "Successfully subscribed to all task events",
                        },
                    )
                    await websocket.send_text(confirm.to_json())

                elif msg_type == WSMessageType.PING.value:
                    await manager.send_pong(websocket)

                else:
                    await manager.send_error(websocket, f"Unknown message type: {msg_type}")

            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                await manager.send_error(websocket, f"Internal error: {str(e)}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {id(websocket)}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await manager.disconnect(websocket)


@router.get("/stats")
async def get_websocket_stats():
    """Get WebSocket connection statistics."""
    manager = get_connection_manager()
    return {
        "active_connections": manager.get_connection_count(),
    }