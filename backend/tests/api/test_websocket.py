"""WebSocket endpoint tests."""
import asyncio
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.v1.endpoints.websocket import (
    get_connection_manager,
    WSMessageType,
    WSMessage,
)


class TestConnectionManager:
    """Tests for the ConnectionManager class."""

    def test_get_connection_manager_singleton(self):
        """Test that get_connection_manager returns singleton."""
        manager1 = get_connection_manager()
        manager2 = get_connection_manager()
        assert manager1 is manager2

    def test_ws_message_serialization(self):
        """Test WSMessage serialization."""
        msg = WSMessage(
            type=WSMessageType.TASK_PROGRESS,
            data={"task_id": str(uuid4()), "progress_percent": 50},
        )
        json_str = msg.to_json()
        parsed = json.loads(json_str)

        assert parsed["type"] == "task_progress"
        assert parsed["data"]["progress_percent"] == 50
        assert "timestamp" in parsed

    def test_ws_message_deserialization(self):
        """Test WSMessage deserialization."""
        data = json.dumps({
            "type": "subscribe_task",
            "data": {"task_id": str(uuid4())},
            "timestamp": "2024-01-01T00:00:00",
        })
        msg = WSMessage.from_json(data)

        assert msg.type == WSMessageType.SUBSCRIBE_TASK
        assert "task_id" in msg.data


class TestWebSocketEndpoint:
    """Tests for WebSocket endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_websocket_connect_disconnect(self, client):
        """Test basic WebSocket connection and disconnection."""
        with client.websocket_connect("/api/v1/ws") as websocket:
            # Connection established
            pass
        # Connection closed cleanly

    def test_websocket_ping_pong(self, client):
        """Test ping/pong message."""
        with client.websocket_connect("/api/v1/ws") as websocket:
            # Send ping
            websocket.send_json({"type": "ping", "data": {}})

            # Receive pong
            response = websocket.receive_json()
            assert response["type"] == "pong"

    def test_websocket_subscribe_task(self, client):
        """Test subscribing to a task."""
        task_id = str(uuid4())

        with client.websocket_connect("/api/v1/ws") as websocket:
            # Subscribe to task
            websocket.send_json({
                "type": "subscribe_task",
                "data": {"task_id": task_id},
            })

            # Receive confirmation
            response = websocket.receive_json()
            assert response["type"] == "task_status"
            assert response["data"]["task_id"] == task_id
            assert response["data"]["status"] == "subscribed"

    def test_websocket_subscribe_task_invalid_uuid(self, client):
        """Test subscribing with invalid task_id."""
        with client.websocket_connect("/api/v1/ws") as websocket:
            # Subscribe with invalid UUID
            websocket.send_json({
                "type": "subscribe_task",
                "data": {"task_id": "not-a-uuid"},
            })

            # Receive error
            response = websocket.receive_json()
            assert response["type"] == "error"
            assert "Invalid task_id format" in response["data"]["error"]

    def test_websocket_subscribe_task_missing_id(self, client):
        """Test subscribing without task_id."""
        with client.websocket_connect("/api/v1/ws") as websocket:
            # Subscribe without task_id
            websocket.send_json({
                "type": "subscribe_task",
                "data": {},
            })

            # Receive error
            response = websocket.receive_json()
            assert response["type"] == "error"
            assert "Missing task_id" in response["data"]["error"]

    def test_websocket_subscribe_all(self, client):
        """Test subscribing to all task events."""
        with client.websocket_connect("/api/v1/ws") as websocket:
            # Subscribe to all
            websocket.send_json({
                "type": "subscribe_all",
                "data": {},
            })

            # Receive confirmation
            response = websocket.receive_json()
            assert response["type"] == "task_status"
            assert response["data"]["status"] == "subscribed_all"

    def test_websocket_invalid_json(self, client):
        """Test handling of invalid JSON."""
        with client.websocket_connect("/api/v1/ws") as websocket:
            # Send invalid JSON
            websocket.send_text("not json")

            # Receive error
            response = websocket.receive_json()
            assert response["type"] == "error"
            assert "Invalid JSON" in response["data"]["error"]

    def test_websocket_unknown_message_type(self, client):
        """Test handling of unknown message type."""
        with client.websocket_connect("/api/v1/ws") as websocket:
            # Send unknown type
            websocket.send_json({
                "type": "unknown_type",
                "data": {},
            })

            # Receive error
            response = websocket.receive_json()
            assert response["type"] == "error"
            assert "Unknown message type" in response["data"]["error"]


class TestWebSocketBroadcast:
    """Tests for WebSocket broadcast functionality."""

    @pytest.fixture
    def manager(self):
        """Get connection manager."""
        return get_connection_manager()

    @pytest.mark.asyncio
    async def test_broadcast_task_progress(self, manager):
        """Test broadcasting task progress."""
        task_id = uuid4()

        # Broadcast should not raise even with no subscribers
        await manager.broadcast_task_progress(
            task_id=task_id,
            progress_percent=50,
            message="Processing",
            status="running",
        )

        # Verify no subscribers
        assert manager.get_subscriber_count(task_id) == 0

    @pytest.mark.asyncio
    async def test_broadcast_task_status(self, manager):
        """Test broadcasting task status."""
        task_id = uuid4()

        await manager.broadcast_task_status(
            task_id=task_id,
            status="completed",
            message="Task finished",
        )

    @pytest.mark.asyncio
    async def test_broadcast_task_completed(self, manager):
        """Test broadcasting task completion."""
        task_id = uuid4()

        await manager.broadcast_task_completed(
            task_id=task_id,
            result={"output": "success"},
        )

    @pytest.mark.asyncio
    async def test_broadcast_task_failed(self, manager):
        """Test broadcasting task failure."""
        task_id = uuid4()

        await manager.broadcast_task_failed(
            task_id=task_id,
            error="Something went wrong",
        )


class TestWebSocketStats:
    """Tests for WebSocket stats endpoint."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client

    @pytest.mark.asyncio
    async def test_get_websocket_stats(self, client):
        """Test getting WebSocket stats."""
        response = await client.get("/api/v1/ws/stats")
        assert response.status_code == 200
        data = response.json()
        assert "active_connections" in data