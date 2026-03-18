"""Tests for repository layer."""
import pytest
from uuid import UUID

from app.repositories import UserRepository, TaskRepository, ConversationRepository
from app.repositories.snapshot import SnapshotRepository
from app.schemas.user import UserCreate
from app.schemas.task import TaskCreate, TaskType, TaskPriority


class TestUserRepository:
    """Tests for UserRepository."""

    @pytest.mark.asyncio
    async def test_create_user(self, session):
        """Test user creation."""
        repo = UserRepository(session)
        user_data = UserCreate(
            username="newuser",
            email="new@example.com",
            password="password123",
        )
        user = await repo.create(user_data)

        assert user.id is not None
        assert user.username == "newuser"
        assert user.email == "new@example.com"

    @pytest.mark.asyncio
    async def test_get_by_username(self, session, test_user):
        """Test getting user by username."""
        repo = UserRepository(session)
        user = await repo.get_by_username("testuser")

        assert user is not None
        assert user.id == test_user.id

    @pytest.mark.asyncio
    async def test_get_by_email(self, session, test_user):
        """Test getting user by email."""
        repo = UserRepository(session)
        user = await repo.get_by_email("test@example.com")

        assert user is not None
        assert user.id == test_user.id

    @pytest.mark.asyncio
    async def test_get_nonexistent_user(self, session):
        """Test getting nonexistent user returns None."""
        repo = UserRepository(session)
        user = await repo.get_by_username("nonexistent")

        assert user is None


class TestTaskRepository:
    """Tests for TaskRepository."""

    @pytest.mark.asyncio
    async def test_create_task(self, session, test_user):
        """Test task creation."""
        repo = TaskRepository(session)
        task_data = TaskCreate(
            type=TaskType.FEATURE,
            priority=TaskPriority.HIGH,
            description="New feature",
        )
        task = await repo.create(task_data)

        assert task.id is not None
        assert task.type == "feature"
        assert task.priority == "high"

    @pytest.mark.asyncio
    async def test_get_by_status(self, session, test_task):
        """Test getting tasks by status."""
        repo = TaskRepository(session)
        tasks = await repo.get_by_status("pending")

        assert len(tasks) == 1
        assert tasks[0].id == test_task.id

    @pytest.mark.asyncio
    async def test_update_status(self, session, test_task):
        """Test updating task status."""
        repo = TaskRepository(session)
        task = await repo.update_status(test_task.id, "running")

        assert task is not None
        assert task.status == "running"

    @pytest.mark.asyncio
    async def test_get_pending_tasks(self, session, test_task):
        """Test getting pending tasks."""
        repo = TaskRepository(session)
        tasks = await repo.get_pending_tasks()

        assert len(tasks) == 1
        assert tasks[0].status == "pending"


class TestConversationRepository:
    """Tests for ConversationRepository."""

    @pytest.mark.asyncio
    async def test_create_session(self, session):
        """Test creating conversation session."""
        repo = ConversationRepository(session)
        conv = await repo.create_session()

        assert conv.id is not None
        assert conv.status == "active"

    @pytest.mark.asyncio
    async def test_add_message(self, session, test_conversation):
        """Test adding message to conversation."""
        repo = ConversationRepository(session)
        message = await repo.add_message(
            session_id=test_conversation.id,
            role="user",
            content="Hello!",
        )

        assert message.id is not None
        assert message.role == "user"
        assert message.content == "Hello!"

    @pytest.mark.asyncio
    async def test_get_messages(self, session, test_conversation):
        """Test getting messages from conversation."""
        repo = ConversationRepository(session)

        # Add some messages
        await repo.add_message(test_conversation.id, "user", "Message 1")
        await repo.add_message(test_conversation.id, "assistant", "Message 2")

        messages = await repo.get_messages(test_conversation.id)

        assert len(messages) == 2
        assert messages[0].content == "Message 1"
        assert messages[1].content == "Message 2"

    @pytest.mark.asyncio
    async def test_close_session(self, session, test_conversation):
        """Test closing conversation session."""
        repo = ConversationRepository(session)
        conv = await repo.close_session(test_conversation.id)

        assert conv.status == "closed"


class TestSnapshotRepository:
    """Tests for SnapshotRepository."""

    @pytest.mark.asyncio
    async def test_create_snapshot(self, session):
        """Test creating snapshot."""
        repo = SnapshotRepository(session)
        snapshot = await repo.create(
            tree_hash="tree_123",
            message="Initial commit",
        )

        assert snapshot.id is not None
        assert snapshot.tree_hash == "tree_123"

    @pytest.mark.asyncio
    async def test_store_object(self, session):
        """Test storing object."""
        repo = SnapshotRepository(session)
        content = b"Test content"
        obj = await repo.store_object(content)

        assert obj.hash is not None
        assert obj.type == "blob"
        assert obj.content == content
        assert obj.size == len(content)

    @pytest.mark.asyncio
    async def test_object_deduplication(self, session):
        """Test that identical content produces same hash."""
        repo = SnapshotRepository(session)
        content = b"Same content"

        obj1 = await repo.store_object(content)
        obj2 = await repo.store_object(content)

        assert obj1.hash == obj2.hash