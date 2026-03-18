"""Tests for data models."""
import pytest
from datetime import datetime, timedelta
from uuid import UUID

from app.models import (
    User, Task, ConversationSession, ConversationMessage,
    Snapshot, Object, AuditLog, Role, Permission
)


class TestUserModel:
    """Tests for User model."""

    def test_user_creation(self, test_user: User):
        """Test user is created correctly."""
        assert test_user.id is not None
        assert isinstance(test_user.id, UUID)
        assert test_user.username == "testuser"
        assert test_user.email == "test@example.com"
        assert test_user.role == "developer"
        assert test_user.is_active is True

    def test_user_timestamps(self, test_user: User):
        """Test user has timestamps."""
        assert test_user.created_at is not None
        assert test_user.updated_at is not None


class TestTaskModel:
    """Tests for Task model."""

    def test_task_creation(self, test_task: Task):
        """Test task is created correctly."""
        assert test_task.id is not None
        assert isinstance(test_task.id, UUID)
        assert test_task.type == "feature"
        assert test_task.priority == "medium"
        assert test_task.status == "pending"
        assert test_task.description == "Test task description"

    def test_task_default_values(self, test_task: Task):
        """Test task default values."""
        assert test_task.priority == "medium"
        assert test_task.status == "pending"
        assert test_task.timeout_seconds == 300

    def test_task_user_relation(self, test_task: Task, test_user: User):
        """Test task-user relationship."""
        assert test_task.user_id == test_user.id


class TestConversationModel:
    """Tests for Conversation model."""

    @pytest.mark.asyncio
    async def test_conversation_creation(self, test_conversation: ConversationSession):
        """Test conversation session is created correctly."""
        assert test_conversation.id is not None
        assert isinstance(test_conversation.id, UUID)
        assert test_conversation.status == "active"

    @pytest.mark.asyncio
    async def test_conversation_messages(self, session, test_conversation: ConversationSession):
        """Test adding messages to conversation."""
        message = ConversationMessage(
            session_id=test_conversation.id,
            role="user",
            content="Hello, world!",
        )
        session.add(message)
        await session.commit()

        assert message.id is not None
        assert message.role == "user"
        assert message.content == "Hello, world!"


class TestSnapshotModel:
    """Tests for Snapshot model."""

    @pytest.mark.asyncio
    async def test_snapshot_creation(self, session):
        """Test snapshot is created correctly."""
        snapshot = Snapshot(
            id="abc123def456",
            tree_hash="tree_hash_123",
            message="Initial commit",
        )
        session.add(snapshot)
        await session.commit()

        assert snapshot.id == "abc123def456"
        assert snapshot.tree_hash == "tree_hash_123"
        assert snapshot.message == "Initial commit"

    @pytest.mark.asyncio
    async def test_snapshot_parent_relation(self, session):
        """Test snapshot parent-child relationship."""
        parent = Snapshot(
            id="parent_hash",
            tree_hash="tree_hash_1",
            message="Parent commit",
        )
        session.add(parent)
        await session.commit()

        child = Snapshot(
            id="child_hash",
            tree_hash="tree_hash_2",
            parent_id="parent_hash",
            message="Child commit",
        )
        session.add(child)
        await session.commit()

        assert child.parent_id == "parent_hash"


class TestObjectModel:
    """Tests for Object model."""

    @pytest.mark.asyncio
    async def test_object_creation(self, session):
        """Test object is created correctly."""
        content = b"Hello, world!"
        obj = Object(
            hash="content_hash_123",
            type="blob",
            content=content,
            size=len(content),
        )
        session.add(obj)
        await session.commit()

        assert obj.hash == "content_hash_123"
        assert obj.type == "blob"
        assert obj.content == content
        assert obj.size == 13


class TestAuditLogModel:
    """Tests for AuditLog model."""

    @pytest.mark.asyncio
    async def test_audit_log_creation(self, session, test_user: User):
        """Test audit log is created correctly."""
        log = AuditLog(
            actor_user_id=test_user.id,
            actor_username=test_user.username,
            actor_role=test_user.role,
            action="task.create",
            resource="task",
            result="success",
        )
        session.add(log)
        await session.commit()

        assert log.id is not None
        assert log.action == "task.create"
        assert log.result == "success"


class TestPermissionModel:
    """Tests for Permission model."""

    @pytest.mark.asyncio
    async def test_role_creation(self, session):
        """Test role is created correctly."""
        role = Role(
            name="custom_role",
            description="A custom role",
            permissions=["task:read", "task:write"],
        )
        session.add(role)
        await session.commit()

        assert role.id is not None
        assert role.name == "custom_role"
        assert len(role.permissions) == 2

    @pytest.mark.asyncio
    async def test_permission_creation(self, session):
        """Test permission is created correctly."""
        perm = Permission(
            name="custom:action",
            resource="custom",
            action="action",
            description="Custom permission",
        )
        session.add(perm)
        await session.commit()

        assert perm.id is not None
        assert perm.name == "custom:action"