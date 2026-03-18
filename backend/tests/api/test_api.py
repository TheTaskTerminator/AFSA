"""API endpoint tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.models.conversation import ConversationSession, ConversationMessage
from app.schemas.task import TaskType, TaskPriority, TaskStatus
from app.schemas.conversation import SessionStatus, MessageRole


# ============== Health Endpoint Tests ==============

class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """Test health check returns ok status."""
        response = await client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


# ============== Tasks API Tests ==============

class TestTasksAPI:
    """Tests for Tasks API endpoints."""

    @pytest.mark.asyncio
    async def test_create_task(self, client: AsyncClient):
        """Test creating a new task."""
        task_data = {
            "type": TaskType.FEATURE.value,
            "priority": TaskPriority.MEDIUM.value,
            "description": "Implement user authentication feature",
        }

        response = await client.post("/api/v1/tasks", json=task_data)

        assert response.status_code == 201
        data = response.json()
        assert data["type"] == TaskType.FEATURE.value
        assert data["priority"] == TaskPriority.MEDIUM.value
        assert data["status"] == TaskStatus.PENDING.value
        assert "id" in data
        assert data["description"] == "Implement user authentication feature"

    @pytest.mark.asyncio
    async def test_create_task_with_requirements(self, client: AsyncClient):
        """Test creating a task with structured requirements."""
        task_data = {
            "type": TaskType.FEATURE.value,
            "priority": TaskPriority.HIGH.value,
            "description": "Add user profile page",
            "structured_requirements": [
                {
                    "field": "theme",
                    "type": "select",
                    "options": ["light", "dark"],
                    "default": "light"
                }
            ],
            "constraints": {
                "target_zone": "mutable",
                "affected_modules": ["user", "profile"],
                "timeout_seconds": 600
            }
        }

        response = await client.post("/api/v1/tasks", json=task_data)

        assert response.status_code == 201
        data = response.json()
        assert data["structured_requirements"] is not None
        assert len(data["structured_requirements"]) == 1

    @pytest.mark.asyncio
    async def test_create_task_invalid_type(self, client: AsyncClient):
        """Test creating a task with invalid type."""
        task_data = {
            "type": "invalid_type",
            "priority": TaskPriority.MEDIUM.value,
            "description": "Test task description"
        }

        response = await client.post("/api/v1/tasks", json=task_data)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_task_short_description(self, client: AsyncClient):
        """Test creating a task with too short description."""
        task_data = {
            "type": TaskType.FEATURE.value,
            "priority": TaskPriority.MEDIUM.value,
            "description": "Short"
        }

        response = await client.post("/api/v1/tasks", json=task_data)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_tasks_empty(self, client: AsyncClient):
        """Test listing tasks when empty."""
        response = await client.get("/api/v1/tasks")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_list_tasks_with_data(self, client: AsyncClient):
        """Test listing tasks with data."""
        # Create a task first
        task_data = {
            "type": TaskType.FEATURE.value,
            "priority": TaskPriority.MEDIUM.value,
            "description": "Test task for listing"
        }
        await client.post("/api/v1/tasks", json=task_data)

        # List tasks
        response = await client.get("/api/v1/tasks")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["description"] == "Test task for listing"

    @pytest.mark.asyncio
    async def test_list_tasks_with_status_filter(self, client: AsyncClient):
        """Test listing tasks filtered by status."""
        # Create a task
        task_data = {
            "type": TaskType.FEATURE.value,
            "priority": TaskPriority.MEDIUM.value,
            "description": "Test task for status filter"
        }
        await client.post("/api/v1/tasks", json=task_data)

        # List with status filter
        response = await client.get(
            "/api/v1/tasks",
            params={"status": TaskStatus.PENDING.value}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == TaskStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_list_tasks_pagination(self, client: AsyncClient):
        """Test listing tasks with pagination."""
        # Create multiple tasks
        for i in range(5):
            task_data = {
                "type": TaskType.FEATURE.value,
                "priority": TaskPriority.MEDIUM.value,
                "description": f"Test task number {i} for pagination"
            }
            await client.post("/api/v1/tasks", json=task_data)

        # Get first page
        response = await client.get("/api/v1/tasks", params={"limit": 2, "offset": 0})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Get second page
        response = await client.get("/api/v1/tasks", params={"limit": 2, "offset": 2})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_get_task_by_id(self, client: AsyncClient):
        """Test getting a task by ID."""
        # Create a task
        task_data = {
            "type": TaskType.FEATURE.value,
            "priority": TaskPriority.HIGH.value,
            "description": "Test task for retrieval"
        }
        create_response = await client.post("/api/v1/tasks", json=task_data)
        task_id = create_response.json()["id"]

        # Get the task
        response = await client.get(f"/api/v1/tasks/{task_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id
        assert data["description"] == "Test task for retrieval"

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, client: AsyncClient):
        """Test getting a non-existent task."""
        fake_id = str(uuid4())
        response = await client.get(f"/api/v1/tasks/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_task(self, client: AsyncClient):
        """Test updating a task."""
        # Create a task
        task_data = {
            "type": TaskType.FEATURE.value,
            "priority": TaskPriority.LOW.value,
            "description": "Test task for update"
        }
        create_response = await client.post("/api/v1/tasks", json=task_data)
        task_id = create_response.json()["id"]

        # Update the task
        update_data = {
            "priority": TaskPriority.HIGH.value
        }
        response = await client.patch(f"/api/v1/tasks/{task_id}", json=update_data)

        assert response.status_code == 200
        data = response.json()
        assert data["priority"] == TaskPriority.HIGH.value

    @pytest.mark.asyncio
    async def test_update_task_not_found(self, client: AsyncClient):
        """Test updating a non-existent task."""
        fake_id = str(uuid4())
        update_data = {"priority": TaskPriority.HIGH.value}

        response = await client.patch(f"/api/v1/tasks/{fake_id}", json=update_data)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_task(self, client: AsyncClient):
        """Test cancelling a pending task."""
        # Create a task
        task_data = {
            "type": TaskType.FEATURE.value,
            "priority": TaskPriority.MEDIUM.value,
            "description": "Test task for cancellation"
        }
        create_response = await client.post("/api/v1/tasks", json=task_data)
        task_id = create_response.json()["id"]

        # Cancel the task
        response = await client.delete(f"/api/v1/tasks/{task_id}")

        assert response.status_code == 204

        # Verify task is cancelled
        get_response = await client.get(f"/api/v1/tasks/{task_id}")
        assert get_response.json()["status"] == TaskStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_cancel_running_task_fails(self, client: AsyncClient, session: AsyncSession):
        """Test that cancelling a running task fails."""
        # Create a task directly in database with running status
        task = Task(
            type=TaskType.FEATURE.value,
            priority=TaskPriority.MEDIUM.value,
            status=TaskStatus.RUNNING.value,
            description="Running task that cannot be cancelled",
            timeout_seconds=300,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        task_id = str(task.id)

        # Try to cancel
        response = await client.delete(f"/api/v1/tasks/{task_id}")

        assert response.status_code == 400
        assert "cannot cancel" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_task_progress(self, client: AsyncClient):
        """Test getting task progress."""
        # Create a task
        task_data = {
            "type": TaskType.FEATURE.value,
            "priority": TaskPriority.MEDIUM.value,
            "description": "Test task for progress"
        }
        create_response = await client.post("/api/v1/tasks", json=task_data)
        task_id = create_response.json()["id"]

        # Get progress
        response = await client.get(f"/api/v1/tasks/{task_id}/progress")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert "status" in data
        assert "progress_percent" in data


# ============== Conversations API Tests ==============

class TestConversationsAPI:
    """Tests for Conversations API endpoints."""

    @pytest.mark.asyncio
    async def test_create_conversation(self, client: AsyncClient):
        """Test creating a new conversation session."""
        response = await client.post("/api/v1/conversations")

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == SessionStatus.ACTIVE.value
        assert data["messages"] == []

    @pytest.mark.asyncio
    async def test_create_conversation_with_user(self, client: AsyncClient):
        """Test creating a conversation with user association."""
        user_id = str(uuid4())
        conv_data = {"user_id": user_id}

        response = await client.post("/api/v1/conversations", json=conv_data)

        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == user_id

    @pytest.mark.asyncio
    async def test_create_conversation_with_ttl(self, client: AsyncClient):
        """Test creating a conversation with expiration time."""
        conv_data = {"expires_in_seconds": 3600}

        response = await client.post("/api/v1/conversations", json=conv_data)

        assert response.status_code == 201
        data = response.json()
        assert data["expires_at"] is not None

    @pytest.mark.asyncio
    async def test_get_conversation(self, client: AsyncClient):
        """Test getting a conversation by ID."""
        # Create a conversation
        create_response = await client.post("/api/v1/conversations")
        conv_id = create_response.json()["id"]

        # Get the conversation
        response = await client.get(f"/api/v1/conversations/{conv_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == conv_id

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, client: AsyncClient):
        """Test getting a non-existent conversation."""
        fake_id = str(uuid4())
        response = await client.get(f"/api/v1/conversations/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_conversations_empty(self, client: AsyncClient):
        """Test listing conversations when empty."""
        response = await client.get("/api/v1/conversations")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_send_message(
        self, client: AsyncClient, session: AsyncSession
    ):
        """Test sending a message in a conversation."""
        # Create a conversation directly in DB to avoid PM Agent mock issues
        conv = ConversationSession(
            status=SessionStatus.ACTIVE.value,
        )
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        conv_id = str(conv.id)

        # Mock the PM Agent
        with patch("app.api.v1.endpoints.conversations.get_pm_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.process_message = AsyncMock(return_value=MagicMock(
                content="I understand you need a login feature.",
                success=True,
                clarification_questions=["What authentication method?"],
                task_card=None,
            ))
            mock_get_agent.return_value = mock_agent

            # Send a message
            message_data = {
                "content": "I need to implement a login feature"
            }
            response = await client.post(
                f"/api/v1/conversations/{conv_id}/messages",
                json=message_data
            )

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == MessageRole.ASSISTANT.value
        assert "login" in data["content"].lower()

    @pytest.mark.asyncio
    async def test_send_message_to_closed_conversation(
        self, client: AsyncClient, session: AsyncSession
    ):
        """Test sending message to a closed conversation fails."""
        # Create a closed conversation
        conv = ConversationSession(
            status=SessionStatus.CLOSED.value,
        )
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        conv_id = str(conv.id)

        # Try to send a message
        message_data = {"content": "Test message"}
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json=message_data
        )

        assert response.status_code == 400
        assert "cannot send message" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_send_message_empty_content(self, client: AsyncClient):
        """Test sending empty message fails validation."""
        # Create a conversation
        create_response = await client.post("/api/v1/conversations")
        conv_id = create_response.json()["id"]

        # Try to send empty message
        message_data = {"content": ""}
        response = await client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json=message_data
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_messages(self, client: AsyncClient, session: AsyncSession):
        """Test getting messages from a conversation."""
        # Create a conversation with messages
        conv = ConversationSession(
            status=SessionStatus.ACTIVE.value,
        )
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        conv_id = conv.id

        # Add messages
        msg1 = ConversationMessage(
            session_id=conv_id,
            role=MessageRole.USER.value,
            content="Hello",
        )
        msg2 = ConversationMessage(
            session_id=conv_id,
            role=MessageRole.ASSISTANT.value,
            content="Hi there!",
        )
        session.add_all([msg1, msg2])
        await session.commit()

        # Get messages
        response = await client.get(f"/api/v1/conversations/{conv_id}/messages")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_close_conversation(self, client: AsyncClient):
        """Test closing a conversation."""
        # Create a conversation
        create_response = await client.post("/api/v1/conversations")
        conv_id = create_response.json()["id"]

        # Close the conversation
        response = await client.delete(f"/api/v1/conversations/{conv_id}")

        assert response.status_code == 204

        # Verify it's closed
        get_response = await client.get(f"/api/v1/conversations/{conv_id}")
        assert get_response.json()["status"] == SessionStatus.CLOSED.value

    @pytest.mark.asyncio
    async def test_get_session_state(self, client: AsyncClient, session: AsyncSession):
        """Test getting session state."""
        # Create a conversation
        conv = ConversationSession(
            status=SessionStatus.ACTIVE.value,
        )
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        conv_id = str(conv.id)

        # Mock PM Agent
        with patch("app.api.v1.endpoints.conversations.get_pm_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.get_session_state = MagicMock(return_value={
                "message_count": 0,
                "is_complete": False,
            })
            mock_get_agent.return_value = mock_agent

            # Get state
            response = await client.get(f"/api/v1/conversations/{conv_id}/state")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == conv_id
        assert "status" in data
        assert "message_count" in data

    @pytest.mark.asyncio
    async def test_generate_task_card(
        self, client: AsyncClient, session: AsyncSession
    ):
        """Test generating a task card from conversation."""
        # Create an active conversation
        conv = ConversationSession(
            status=SessionStatus.ACTIVE.value,
        )
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        conv_id = str(conv.id)

        # Mock PM Agent
        with patch("app.api.v1.endpoints.conversations.get_pm_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.generate_task_card = AsyncMock(return_value=MagicMock(
                id="task-card-123",
                type="feature",
                priority="high",
                description="Implement login feature",
                structured_requirements=[],
                constraints={},
            ))
            mock_get_agent.return_value = mock_agent

            # Generate task card
            response = await client.post(f"/api/v1/conversations/{conv_id}/task-card")

        assert response.status_code == 200
        data = response.json()
        assert "task_card" in data
        assert data["task_card"]["type"] == "feature"

    @pytest.mark.asyncio
    async def test_generate_task_card_insufficient_context(
        self, client: AsyncClient, session: AsyncSession
    ):
        """Test generating task card with insufficient context."""
        # Create an active conversation
        conv = ConversationSession(
            status=SessionStatus.ACTIVE.value,
        )
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        conv_id = str(conv.id)

        # Mock PM Agent returning None (insufficient context)
        with patch("app.api.v1.endpoints.conversations.get_pm_agent") as mock_get_agent:
            mock_agent = MagicMock()
            mock_agent.generate_task_card = AsyncMock(return_value=None)
            mock_get_agent.return_value = mock_agent

            # Try to generate task card
            response = await client.post(f"/api/v1/conversations/{conv_id}/task-card")

        assert response.status_code == 400
        assert "insufficient context" in response.json()["detail"].lower()


# ============== Error Handling Tests ==============

class TestAPIErrorHandling:
    """Tests for API error handling."""

    @pytest.mark.asyncio
    async def test_invalid_uuid_format(self, client: AsyncClient):
        """Test that invalid UUID format returns proper error."""
        response = await client.get("/api/v1/tasks/not-a-uuid")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_json_body(self, client: AsyncClient):
        """Test that invalid JSON body returns proper error."""
        response = await client.post(
            "/api/v1/tasks",
            content="not json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, client: AsyncClient):
        """Test that missing required fields returns proper error."""
        task_data = {
            "type": TaskType.FEATURE.value,
            # missing description
        }

        response = await client.post("/api/v1/tasks", json=task_data)

        assert response.status_code == 422