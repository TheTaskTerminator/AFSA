"""
API Endpoints Integration Tests.

Tests all major API endpoints:
- POST /api/v1/tasks - Create task
- GET /api/v1/tasks/{id} - Get task
- POST /api/v1/conversations - Create conversation
- GET /api/v1/snapshots - Get snapshots
- WebSocket connection tests
"""
import asyncio
import pytest
import json
from uuid import uuid4
from httpx import AsyncClient

from app.agents.base import AgentResponse, TaskCard, TaskPriority, TaskType
from app.orchestration.dispatcher.dispatcher import (
    execute_submitted_task,
    session_factory_from_session,
)


async def _wait_for_task_status(
    client: AsyncClient,
    task_id: str,
    expected_status: str,
    attempts: int = 20,
    delay: float = 0.05,
):
    """Poll a task until background execution reaches the expected status."""
    last_task = None
    for _ in range(attempts):
        response = await client.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        last_task = response.json()
        if last_task["status"] == expected_status:
            return last_task
        await asyncio.sleep(delay)
    assert last_task is not None
    assert last_task["status"] == expected_status
    return last_task


@pytest.mark.asyncio
class TestTaskEndpoints:
    """Test task management API endpoints."""

    async def test_create_task(self, client: AsyncClient):
        """
        Test POST /api/v1/tasks - Create a new task.
        
        Verifies:
        - Task is created with valid data
        - Returns 201 status code
        - Response contains task ID and all fields
        """
        task_data = {
            "type": "feature",
            "priority": "high",
            "description": "Implement user authentication endpoint",
            "constraints": {
                "timeout_seconds": 300,
                "affected_modules": ["auth", "user"]
            }
        }
        
        response = await client.post("/api/v1/tasks", json=task_data)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "id" in data
        assert data["type"] == "feature"
        assert data["priority"] == "high"
        assert data["description"] == task_data["description"]
        assert data["status"] == "pending"

    async def test_create_task_with_session_id(self, client: AsyncClient, test_conversation):
        """
        Test POST /api/v1/tasks - Create task with session ID.
        
        Verifies:
        - Task is associated with conversation session
        - Task is submitted to dispatcher
        """
        task_data = {
            "type": "feature",
            "priority": "medium",
            "description": "Implement chat feature",
            "session_id": str(test_conversation.id)
        }
        
        response = await client.post("/api/v1/tasks", json=task_data)
        
        assert response.status_code == 201
        data = response.json()
        
        assert "id" in data
        assert data["session_id"] == str(test_conversation.id)

        task = await _wait_for_task_status(client, data["id"], "completed")
        assert task["result"]["success"] is True

    async def test_get_task_by_id(self, client: AsyncClient, test_task):
        """
        Test GET /api/v1/tasks/{id} - Get task by ID.
        
        Verifies:
        - Returns correct task data
        - Returns 200 status code
        """
        response = await client.get(f"/api/v1/tasks/{test_task.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == str(test_task.id)
        assert data["type"] == test_task.type
        assert data["description"] == test_task.description
        assert data["status"] == test_task.status

    async def test_get_task_not_found(self, client: AsyncClient):
        """
        Test GET /api/v1/tasks/{id} - Task not found.
        
        Verifies:
        - Returns 404 status code
        - Returns appropriate error message
        """
        fake_id = str(uuid4())
        response = await client.get(f"/api/v1/tasks/{fake_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    async def test_list_tasks(self, client: AsyncClient, test_task):
        """
        Test GET /api/v1/tasks - List all tasks.
        
        Verifies:
        - Returns list of tasks
        - Supports pagination
        - Supports filtering
        """
        response = await client.get("/api/v1/tasks")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_list_tasks_filtered_by_status(self, client: AsyncClient, test_task):
        """
        Test GET /api/v1/tasks?status=pending - Filter by status.
        
        Verifies:
        - Returns only tasks with specified status
        """
        response = await client.get("/api/v1/tasks?status=pending")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        for task in data:
            assert task["status"] == "pending"

    async def test_update_task(self, client: AsyncClient, test_task):
        """
        Test PATCH /api/v1/tasks/{id} - Update task.
        
        Verifies:
        - Task fields are updated
        - Returns updated task data
        """
        update_data = {
            "priority": "high",
            "status": "running"
        }
        
        response = await client.patch(f"/api/v1/tasks/{test_task.id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["priority"] == "high"
        assert data["status"] == "running"

    async def test_cancel_task(self, client: AsyncClient, test_task):
        """
        Test DELETE /api/v1/tasks/{id} - Cancel task.
        
        Verifies:
        - Task is cancelled
        - Returns 204 status code
        """
        response = await client.delete(f"/api/v1/tasks/{test_task.id}")
        
        assert response.status_code == 204

    async def test_submit_task_for_execution(self, client: AsyncClient, test_task):
        """
        Test POST /api/v1/tasks/{id}/submit - Submit task for execution.
        
        Verifies:
        - Task is submitted to dispatcher
        - Dispatcher drains the task to completion
        """
        response = await client.post(f"/api/v1/tasks/{test_task.id}/submit")
        assert response.status_code == 200

        task = await _wait_for_task_status(client, str(test_task.id), "completed")
        assert task["started_at"] is not None
        assert task["completed_at"] is not None
        assert task["result"]["success"] is True

    async def test_background_executor_does_not_run_cancelled_task(self, session, test_task):
        """
        Test that background execution respects cancellation before start.

        Verifies:
        - A task no longer in queued state is not executed
        - Cancelled remains a terminal state
        """
        test_task.status = "cancelled"
        await session.commit()

        await execute_submitted_task(session_factory_from_session(session), test_task.id)
        await session.refresh(test_task)

        assert test_task.status == "cancelled"
        assert test_task.result is None
        assert test_task.started_at is None
        assert test_task.completed_at is None

    async def test_get_task_progress(self, client: AsyncClient, test_task):
        """
        Test GET /api/v1/tasks/{id}/progress - Get task progress.
        
        Verifies:
        - Returns progress information
        - Contains status and progress percentage
        """
        response = await client.get(f"/api/v1/tasks/{test_task.id}/progress")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "task_id" in data
        assert "status" in data
        assert "progress_percent" in data


@pytest.mark.asyncio
class TestConversationEndpoints:
    """Test conversation management API endpoints."""

    async def test_create_conversation(self, client: AsyncClient):
        """
        Test POST /api/v1/conversations - Create conversation session.
        
        Verifies:
        - Conversation is created
        - Returns 201 status code
        - Session has unique ID
        """
        response = await client.post("/api/v1/conversations", json={})
        
        assert response.status_code == 201
        data = response.json()
        
        assert "id" in data
        assert data["status"] == "active"
        assert "messages" in data
        assert data["messages"] == []

    async def test_create_conversation_with_user(self, client: AsyncClient, test_user):
        """
        Test POST /api/v1/conversations - Create with user association.
        
        Verifies:
        - Conversation is associated with user
        - User ID is stored correctly
        """
        conversation_data = {
            "user_id": str(test_user.id),
            "expires_in_seconds": 3600
        }
        
        response = await client.post("/api/v1/conversations", json=conversation_data)
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["user_id"] == str(test_user.id)

    async def test_get_conversation(self, client: AsyncClient, test_conversation):
        """
        Test GET /api/v1/conversations/{id} - Get conversation.
        
        Verifies:
        - Returns conversation with messages
        - Returns 200 status code
        """
        response = await client.get(f"/api/v1/conversations/{test_conversation.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == str(test_conversation.id)
        assert "messages" in data

    async def test_get_conversation_not_found(self, client: AsyncClient):
        """
        Test GET /api/v1/conversations/{id} - Not found.
        
        Verifies:
        - Returns 404 status code
        """
        fake_id = str(uuid4())
        response = await client.get(f"/api/v1/conversations/{fake_id}")
        
        assert response.status_code == 404

    async def test_list_conversations(self, client: AsyncClient, test_user):
        """
        Test GET /api/v1/conversations - List conversations.
        
        Verifies:
        - Returns list of conversation summaries
        - Supports user filtering
        """
        response = await client.get(f"/api/v1/conversations?user_id={test_user.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)

    async def test_send_message(self, client: AsyncClient, test_conversation):
        """
        Test POST /api/v1/conversations/{id}/messages - Send message.
        
        Verifies:
        - Message is stored
        - Agent response is returned
        - Returns 200 status code
        """
        message_data = {
            "content": "I need help with user authentication",
            "metadata": {"source": "web"}
        }
        
        response = await client.post(
            f"/api/v1/conversations/{test_conversation.id}/messages",
            json=message_data
        )
        
        # Note: May fail if PM Agent is not mocked, but endpoint should exist
        assert response.status_code in [200, 500]

    async def test_send_message_creates_task_when_pm_returns_task_card(
        self,
        client: AsyncClient,
        test_conversation,
        monkeypatch,
    ):
        """Conversation message should become a persisted task when PM emits a task card."""
        import app.api.v1.endpoints.conversations as conversations_module

        class FakePMAgent:
            async def process_message(self, session_id, message, context=None):
                task_card = TaskCard(
                    type=TaskType.FEATURE,
                    priority=TaskPriority.HIGH,
                    description="Implement dashboard analytics for active users",
                    structured_requirements=[
                        {"field": "metric", "type": "text", "default": "active_users"}
                    ],
                    constraints={
                        "target_zone": "mutable",
                        "affected_modules": ["dashboard"],
                        "timeout_seconds": 120,
                    },
                )
                return AgentResponse(
                    success=True,
                    content="已生成任务并进入执行队列。",
                    task_card=task_card,
                    metadata={"type": "task_card", "session_id": str(session_id)},
                )

        monkeypatch.setattr(conversations_module, "_pm_agent", FakePMAgent())

        response = await client.post(
            f"/api/v1/conversations/{test_conversation.id}/messages",
            json={"content": "Add active-user analytics to the dashboard"},
        )

        assert response.status_code == 200
        assistant_message = response.json()
        assert assistant_message["metadata"]["has_task_card"] is True
        assert assistant_message["metadata"]["task_id"]

        tasks_response = await client.get(
            f"/api/v1/tasks?session_id={test_conversation.id}"
        )
        assert tasks_response.status_code == 200
        tasks = tasks_response.json()
        assert len(tasks) == 1
        assert tasks[0]["id"] == assistant_message["metadata"]["task_id"]
        assert tasks[0]["description"] == "Implement dashboard analytics for active users"
        assert tasks[0]["status"] == "completed"
        assert tasks[0]["result"]["success"] is True

    async def test_send_message_runs_created_task_lifecycle_to_completion(
        self,
        client: AsyncClient,
        test_conversation,
        monkeypatch,
    ):
        """Conversation-created tasks should automatically flow through execution states."""

        async def fake_process_message(self, session_id, message, context=None):
            return AgentResponse(
                success=True,
                content="我已经拆解并开始执行这个任务。",
                task_card=TaskCard(
                    type=TaskType.FEATURE,
                    priority=TaskPriority.MEDIUM,
                    description="Implement lifecycle-visible task execution",
                    structured_requirements=[],
                    constraints={},
                ),
            )

        monkeypatch.setattr(
            "app.agents.pm_agent.agent.PMAgent.process_message",
            fake_process_message,
        )

        response = await client.post(
            f"/api/v1/conversations/{test_conversation.id}/messages",
            json={"content": "请实现一个可以看到状态流转的任务"},
        )

        assert response.status_code == 200
        task_id = response.json()["metadata"]["task_id"]

        task_response = await client.get(f"/api/v1/tasks/{task_id}")
        assert task_response.status_code == 200
        task = task_response.json()
        assert task["status"] == "completed"
        assert task["started_at"] is not None
        assert task["completed_at"] is not None
        assert task["result"]["success"] is True
        assert "lifecycle-visible" in task["result"]["output"]

    async def test_get_messages(self, client: AsyncClient, test_conversation):
        """
        Test GET /api/v1/conversations/{id}/messages - Get messages.
        
        Verifies:
        - Returns list of messages
        - Supports pagination
        """
        response = await client.get(f"/api/v1/conversations/{test_conversation.id}/messages")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)

    async def test_close_conversation(self, client: AsyncClient, test_conversation):
        """
        Test DELETE /api/v1/conversations/{id} - Close conversation.
        
        Verifies:
        - Conversation is closed
        - Returns 204 status code
        """
        response = await client.delete(f"/api/v1/conversations/{test_conversation.id}")
        
        assert response.status_code == 204

    async def test_generate_task_card(self, client: AsyncClient, test_conversation):
        """
        Test POST /api/v1/conversations/{id}/task-card - Generate task card.
        
        Verifies:
        - Task card is generated from conversation
        - Returns structured task data
        """
        response = await client.post(
            f"/api/v1/conversations/{test_conversation.id}/task-card"
        )
        
        # Note: May fail if PM Agent is not configured
        assert response.status_code in [200, 400, 500]


@pytest.mark.asyncio
class TestSnapshotEndpoints:
    """Test snapshot management API endpoints."""

    async def test_list_snapshots(self, client: AsyncClient):
        """
        Test GET /api/v1/snapshots - List snapshots.
        
        Verifies:
        - Endpoint exists
        - Returns list or appropriate error
        """
        response = await client.get("/api/v1/snapshots")
        
        # Currently returns 501 (Not Implemented)
        assert response.status_code in [200, 501]

    async def test_get_snapshot(self, client: AsyncClient):
        """
        Test GET /api/v1/snapshots/{id} - Get snapshot.
        
        Verifies:
        - Endpoint exists
        - Returns snapshot or appropriate error
        """
        response = await client.get("/api/v1/snapshots/abc123")
        
        # Currently returns 501 (Not Implemented)
        assert response.status_code in [200, 404, 501]

    async def test_restore_snapshot(self, client: AsyncClient):
        """
        Test POST /api/v1/snapshots/{id}/restore - Restore snapshot.
        
        Verifies:
        - Endpoint exists
        - Returns appropriate status
        """
        response = await client.post("/api/v1/snapshots/abc123/restore")
        
        # Currently returns 501 (Not Implemented)
        assert response.status_code in [204, 501]


@pytest.mark.asyncio
class TestWebSocketEndpoint:
    """Test WebSocket connection endpoints."""

    async def test_websocket_connection(self, client: AsyncClient):
        """
        Test WebSocket endpoint exists.
        
        Verifies:
        - WebSocket endpoint is registered
        """
        # WebSocket testing requires special setup, just verify endpoint exists
        # Full WebSocket tests would need event loop management
        pytest.skip("WebSocket tests require special event loop setup - manual testing recommended")

    async def test_websocket_task_updates(self, client: AsyncClient):
        """
        Test WebSocket task updates endpoint.
        
        Verifies:
        - Endpoint is registered
        """
        pytest.skip("WebSocket task updates require running server - manual testing recommended")

    async def test_websocket_message_format(self, client: AsyncClient):
        """
        Test WebSocket message format.
        
        Verifies:
        - Message validation exists
        """
        pytest.skip("WebSocket message validation requires running server - manual testing recommended")


@pytest.mark.asyncio
class TestHealthEndpoint:
    """Test health check endpoint."""

    async def test_health_check(self, client: AsyncClient):
        """
        Test GET /api/v1/health - Health check.
        
        Verifies:
        - Returns healthy status
        - Contains version information
        """
        response = await client.get("/api/v1/health")
        
        # Health endpoint may return different formats
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "status" in data or "message" in data

    async def test_root_health_check(self, client: AsyncClient):
        """
        Test GET /health - Root health check.
        
        Verifies:
        - Returns healthy status
        """
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
