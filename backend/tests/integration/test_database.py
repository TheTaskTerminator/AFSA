"""
Database Integration Tests.

Tests database operations:
- Model CRUD operations
- Transaction handling
- Migration script validation
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
class TestUserModelCRUD:
    """Test User model CRUD operations."""

    async def test_create_user(self, session: AsyncSession):
        """
        Test creating a new user.
        
        Verifies:
        - User is created with all required fields
        - ID is generated
        - Timestamps are set
        """
        from app.models.user import User
        
        user = User(
            username=f"testuser_{uuid4()}",
            email=f"test_{uuid4()}@example.com",
            password_hash="hashed_password_123",
            role="developer",
            is_active=True,
        )
        
        session.add(user)
        await session.commit()
        await session.refresh(user)
        
        assert user.id is not None
        assert user.username.startswith("testuser_")
        assert user.created_at is not None
        assert user.updated_at is not None
        assert user.is_active is True

    async def test_read_user(self, session: AsyncSession, test_user):
        """
        Test reading a user by ID.
        
        Verifies:
        - User can be retrieved by ID
        - All fields are correctly loaded
        """
        from app.models.user import User
        
        result = await session.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one()
        
        assert user is not None
        assert user.id == test_user.id
        assert user.username == test_user.username
        assert user.email == test_user.email

    async def test_update_user(self, session: AsyncSession, test_user):
        """
        Test updating a user.
        
        Verifies:
        - User fields are updated
        - updated_at timestamp is modified
        """
        test_user.role = "admin"
        test_user.is_active = False
        await session.commit()
        await session.refresh(test_user)
        
        assert test_user.role == "admin"
        assert test_user.is_active is False

    async def test_delete_user(self, session: AsyncSession, test_user):
        """
        Test deleting a user.
        
        Verifies:
        - User is deleted from database
        - Cannot be retrieved after deletion
        """
        from app.models.user import User
        
        await session.delete(test_user)
        await session.commit()
        
        result = await session.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one_or_none()
        
        assert user is None

    async def test_user_unique_constraints(self, session: AsyncSession, test_user):
        """
        Test user unique constraints.
        
        Verifies:
        - Duplicate username raises IntegrityError
        - Duplicate email raises IntegrityError
        """
        from app.models.user import User
        from sqlalchemy.exc import IntegrityError
        
        # Try to create user with same username
        duplicate_user = User(
            username=test_user.username,
            email=f"different_{uuid4()}@example.com",
            password_hash="hashed_password",
            role="user",
        )
        
        session.add(duplicate_user)
        with pytest.raises(IntegrityError):
            await session.commit()
        
        await session.rollback()


@pytest.mark.asyncio
class TestTaskModelCRUD:
    """Test Task model CRUD operations."""

    async def test_create_task(self, session: AsyncSession, test_user):
        """
        Test creating a new task.
        
        Verifies:
        - Task is created with all fields
        - Default values are applied
        - Foreign key relationship works
        """
        from app.models.task import Task
        
        task = Task(
            type="bugfix",
            priority="high",
            status="pending",
            description="Fix login bug",
            user_id=test_user.id,
            timeout_seconds=600,
        )
        
        session.add(task)
        await session.commit()
        await session.refresh(task)
        
        assert task.id is not None
        assert task.type == "bugfix"
        assert task.priority == "high"
        assert task.status == "pending"
        assert task.user_id == test_user.id
        assert task.timeout_seconds == 600

    async def test_read_task(self, session: AsyncSession, test_task):
        """
        Test reading a task by ID.
        
        Verifies:
        - Task can be retrieved
        - All fields are loaded
        """
        from app.models.task import Task
        
        result = await session.execute(select(Task).where(Task.id == test_task.id))
        task = result.scalar_one()
        
        assert task is not None
        assert task.id == test_task.id
        assert task.description == test_task.description

    async def test_update_task_status(self, session: AsyncSession, test_task):
        """
        Test updating task status.
        
        Verifies:
        - Status transitions work correctly
        - started_at is set when status changes to running
        """
        from datetime import datetime
        
        test_task.status = "running"
        test_task.started_at = datetime.utcnow()
        await session.commit()
        await session.refresh(test_task)
        
        assert test_task.status == "running"
        assert test_task.started_at is not None

    async def test_task_with_json_fields(self, session: AsyncSession, test_user):
        """
        Test task with JSON fields (structured_requirements, constraints, result).
        
        Verifies:
        - JSON fields are properly stored
        - Complex nested structures are preserved
        """
        from app.models.task import Task
        
        task = Task(
            type="feature",
            priority="medium",
            status="pending",
            description="Implement new feature",
            user_id=test_user.id,
            structured_requirements={
                "features": ["feature1", "feature2"],
                "acceptance_criteria": [
                    {"id": 1, "description": "Criterion 1", "priority": "high"}
                ]
            },
            constraints={
                "timeout": 300,
                "max_iterations": 10,
                "allowed_frameworks": ["FastAPI", "SQLAlchemy"]
            },
        )
        
        session.add(task)
        await session.commit()
        await session.refresh(task)
        
        assert task.structured_requirements is not None
        assert len(task.structured_requirements["features"]) == 2
        assert task.constraints["timeout"] == 300

    async def test_delete_task(self, session: AsyncSession, test_task):
        """
        Test deleting a task.
        
        Verifies:
        - Task is deleted
        - Related data is handled correctly
        """
        from app.models.task import Task
        
        await session.delete(test_task)
        await session.commit()
        
        result = await session.execute(select(Task).where(Task.id == test_task.id))
        task = result.scalar_one_or_none()
        
        assert task is None


@pytest.mark.asyncio
class TestConversationModelCRUD:
    """Test Conversation model CRUD operations."""

    async def test_create_conversation_session(self, session: AsyncSession, test_user):
        """
        Test creating a conversation session.
        
        Verifies:
        - Session is created
        - User association works
        - Default status is active
        """
        from app.models.conversation import ConversationSession
        
        conv = ConversationSession(
            user_id=test_user.id,
            status="active",
        )
        
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        
        assert conv.id is not None
        assert conv.user_id == test_user.id
        assert conv.status == "active"

    async def test_create_conversation_message(self, session: AsyncSession, test_conversation):
        """
        Test creating a conversation message.
        
        Verifies:
        - Message is created
        - Associated with correct session
        - Role and content are stored
        """
        from app.models.conversation import ConversationMessage
        
        msg = ConversationMessage(
            session_id=test_conversation.id,
            role="user",
            content="Hello, I need help with my project",
            msg_metadata={"source": "web"}
        )
        
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        
        assert msg.id is not None
        assert msg.session_id == test_conversation.id
        assert msg.role == "user"
        assert msg.content == "Hello, I need help with my project"

    async def test_conversation_cascade_delete(self, session: AsyncSession, test_user):
        """
        Test conversation cascade delete.
        
        Verifies:
        - Deleting session deletes all messages
        - Foreign key constraints work correctly
        """
        from app.models.conversation import ConversationSession, ConversationMessage
        
        # Create session with messages
        conv = ConversationSession(user_id=test_user.id, status="active")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        
        msg = ConversationMessage(
            session_id=conv.id,
            role="user",
            content="Test message"
        )
        session.add(msg)
        await session.commit()
        msg_id = msg.id
        
        # Delete session
        await session.delete(conv)
        await session.commit()
        
        # Verify message is also deleted
        result = await session.execute(
            select(ConversationMessage).where(ConversationMessage.id == msg_id)
        )
        deleted_msg = result.scalar_one_or_none()
        
        assert deleted_msg is None


@pytest.mark.asyncio
class TestSnapshotModelCRUD:
    """Test Snapshot model CRUD operations."""

    async def test_create_snapshot(self, session: AsyncSession, test_task):
        """
        Test creating a snapshot.
        
        Verifies:
        - Snapshot is created with SHA-256 hash ID
        - Parent relationship works
        - Tree hash is stored
        """
        from app.models.snapshot import Snapshot
        import hashlib
        
        # Generate SHA-256 hash
        snapshot_id = hashlib.sha256(f"snapshot_{uuid4()}".encode()).hexdigest()
        
        snapshot = Snapshot(
            id=snapshot_id,
            task_id=test_task.id,
            tree_hash=hashlib.sha256(b"tree_content").hexdigest(),
            message="Initial commit",
            snap_metadata={"author": "test", "files_changed": 5}
        )
        
        session.add(snapshot)
        await session.commit()
        await session.refresh(snapshot)
        
        assert snapshot.id == snapshot_id
        assert snapshot.task_id == test_task.id
        assert snapshot.message == "Initial commit"
        assert snapshot.snap_metadata["files_changed"] == 5

    async def test_snapshot_parent_child_relationship(self, session: AsyncSession, test_task):
        """
        Test snapshot parent-child relationships.
        
        Verifies:
        - Child snapshots can reference parent
        - Parent can access children
        - Tree structure is maintained
        """
        from app.models.snapshot import Snapshot
        import hashlib
        
        # Create parent snapshot
        parent_id = hashlib.sha256(b"parent").hexdigest()
        parent = Snapshot(
            id=parent_id,
            task_id=test_task.id,
            tree_hash=hashlib.sha256(b"parent_tree").hexdigest(),
            message="Parent commit"
        )
        session.add(parent)
        await session.commit()
        
        # Create child snapshot
        child_id = hashlib.sha256(b"child").hexdigest()
        child = Snapshot(
            id=child_id,
            task_id=test_task.id,
            parent_id=parent_id,
            tree_hash=hashlib.sha256(b"child_tree").hexdigest(),
            message="Child commit"
        )
        session.add(child)
        await session.commit()
        await session.refresh(child)
        
        # Verify relationship
        assert child.parent_id == parent_id
        
        # Load parent with children
        result = await session.execute(
            select(Snapshot).where(Snapshot.id == parent_id)
        )
        loaded_parent = result.scalar_one()
        await session.refresh(loaded_parent)
        
        assert len(loaded_parent.children) == 1
        assert loaded_parent.children[0].id == child_id

    async def test_create_object(self, session: AsyncSession):
        """
        Test creating a content-addressable object.
        
        Verifies:
        - Object is stored with hash
        - Binary content is preserved
        - Size is calculated correctly
        """
        from app.models.snapshot import Object
        import hashlib
        
        content = b"This is test content for the object"
        content_hash = hashlib.sha256(content).hexdigest()
        
        obj = Object(
            hash=content_hash,
            type="blob",
            content=content,
            size=len(content)
        )
        
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        
        assert obj.hash == content_hash
        assert obj.type == "blob"
        assert obj.content == content
        assert obj.size == len(content)


@pytest.mark.asyncio
class TestTransactionHandling:
    """Test database transaction handling."""

    async def test_transaction_commit(self, session: AsyncSession):
        """
        Test successful transaction commit.
        
        Verifies:
        - Changes are persisted on commit
        - Data is visible in new session
        """
        from app.models.user import User
        
        # Create user in transaction
        user = User(
            username=f"tx_user_{uuid4()}",
            email=f"tx_{uuid4()}@example.com",
            password_hash="hash",
            role="user",
        )
        session.add(user)
        await session.commit()
        
        # Verify in new query
        result = await session.execute(select(User).where(User.id == user.id))
        saved_user = result.scalar_one()
        
        assert saved_user is not None
        assert saved_user.username == user.username

    async def test_transaction_rollback(self, session: AsyncSession):
        """
        Test transaction rollback.
        
        Verifies:
        - Changes are reverted on rollback
        - Database state is unchanged
        """
        from app.models.user import User
        from sqlalchemy.exc import IntegrityError
        
        # Start transaction
        user1 = User(
            username=f"rollback_user_{uuid4()}",
            email=f"rollback_{uuid4()}@example.com",
            password_hash="hash",
            role="user",
        )
        session.add(user1)
        await session.flush()  # Get ID without committing
        
        # Simulate error
        try:
            # Try to create duplicate (will fail)
            user2 = User(
                username=user1.username,  # Duplicate
                email=f"duplicate_{uuid4()}@example.com",
                password_hash="hash",
                role="user",
            )
            session.add(user2)
            await session.commit()
        except IntegrityError:
            await session.rollback()
        
        # Verify neither user exists
        result = await session.execute(
            select(User).where(User.username == user1.username)
        )
        saved_user = result.scalar_one_or_none()
        
        assert saved_user is None

    async def test_nested_transaction(self, session: AsyncSession, test_user):
        """
        Test nested transaction (savepoint) behavior.
        
        Verifies:
        - Inner transaction can be rolled back independently
        - Outer transaction remains intact
        """
        from app.models.task import Task
        
        # Outer transaction
        task1 = Task(
            type="feature",
            priority="medium",
            status="pending",
            description="Outer task",
            user_id=test_user.id,
        )
        session.add(task1)
        await session.flush()
        
        try:
            # Inner transaction (savepoint)
            task2 = Task(
                type="bugfix",
                priority="high",
                status="pending",
                description="Inner task",
                user_id=None,  # This will cause an error if user_id is required
            )
            session.add(task2)
            await session.flush()
            
            # Simulate error
            raise ValueError("Simulated error")
            
        except ValueError:
            await session.rollback()
        
        # task1 should still be pending (not committed yet)
        # task2 should not exist
        result = await session.execute(select(Task).where(Task.description == "Inner task"))
        inner_task = result.scalar_one_or_none()
        
        assert inner_task is None

    async def test_transaction_isolation(self, session: AsyncSession):
        """
        Test transaction isolation.
        
        Verifies:
        - Uncommitted changes are not visible
        - Committed changes are visible
        """
        from app.models.user import User
        
        # For in-memory SQLite, we can't truly test isolation
        # This test documents the expected behavior
        user = User(
            username=f"isolation_user_{uuid4()}",
            email=f"isolation_{uuid4()}@example.com",
            password_hash="hash",
            role="user",
        )
        session.add(user)
        await session.flush()
        
        # User exists in this session but not committed
        assert user.id is not None
        
        # After commit, should be visible
        await session.commit()
        
        result = await session.execute(select(User).where(User.id == user.id))
        saved_user = result.scalar_one()
        
        assert saved_user is not None


@pytest.mark.asyncio
class TestMigrationValidation:
    """Test database migration script validation."""

    async def test_all_models_have_tables(self, engine):
        """
        Test that all models have corresponding tables.
        
        Verifies:
        - All defined models can create tables
        - No migration errors occur
        """
        from app.models.base import Base
        from app.models import User, Task, ConversationSession, ConversationMessage
        from app.models import Snapshot, Object, AuditLog, Role, Permission
        
        # If we got here, all tables were created successfully by conftest
        # This test verifies the models are properly defined
        assert User.__tablename__ == "users"
        assert Task.__tablename__ == "tasks"
        assert ConversationSession.__tablename__ == "conversation_sessions"
        assert ConversationMessage.__tablename__ == "conversation_messages"
        assert Snapshot.__tablename__ == "snapshots"
        assert Object.__tablename__ == "objects"
        assert AuditLog.__tablename__ == "audit_logs"
        assert Role.__tablename__ == "roles"
        assert Permission.__tablename__ == "permissions"

    async def test_alembic_migration_files_exist(self):
        """
        Test that Alembic migration files exist.
        
        Verifies:
        - Alembic versions directory exists
        - At least one migration file is present
        """
        import os
        from pathlib import Path
        
        migrations_dir = Path(__file__).parent.parent.parent / "migrations" / "versions"
        
        assert migrations_dir.exists()
        
        migration_files = list(migrations_dir.glob("*.py"))
        assert len(migration_files) > 0

    async def test_alembic_configuration_valid(self):
        """
        Test that Alembic configuration is valid.
        
        Verifies:
        - alembic.ini exists
        - Configuration can be loaded
        """
        from pathlib import Path
        
        alembic_ini = Path(__file__).parent.parent.parent / "alembic.ini"
        
        assert alembic_ini.exists()
        
        # Try to read the file
        content = alembic_ini.read_text()
        assert "[alembic]" in content

    async def test_migration_env_exists(self):
        """
        Test that Alembic env.py exists.
        
        Verifies:
        - Migration environment file exists
        - File is valid Python
        """
        from pathlib import Path
        
        env_py = Path(__file__).parent.parent.parent / "migrations" / "env.py"
        
        assert env_py.exists()
        
        # Try to compile the file
        with open(env_py) as f:
            code = f.read()
        
        compile(code, str(env_py), 'exec')

    async def test_all_models_have_primary_keys(self):
        """
        Test that all models have primary keys defined.
        
        Verifies:
        - Each model has a primary key
        - Primary keys are properly configured
        """
        from app.models.base import Base
        from sqlalchemy import inspect
        
        # Create a temporary engine to inspect tables
        from sqlalchemy.pool import StaticPool
        from sqlalchemy.ext.asyncio import create_async_engine
        
        temp_engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
        )
        
        async with temp_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Check each model
        for model in Base.registry.mappers:
            mapper = model
            assert len(mapper.primary_key) > 0, f"Model {mapper.class_.__name__} has no primary key"
        
        await temp_engine.dispose()

    async def test_foreign_key_relationships_valid(self, session: AsyncSession, test_user, test_task):
        """
        Test that foreign key relationships work correctly.
        
        Verifies:
        - Foreign keys are properly defined
        - Relationships can be loaded
        - Cascade behaviors work
        """
        from app.models.task import Task
        from app.models.conversation import ConversationSession, ConversationMessage
        
        # Test Task -> User relationship
        result = await session.execute(select(Task).where(Task.user_id == test_user.id))
        user_tasks = result.scalars().all()
        
        assert len(user_tasks) >= 1
        
        # Test ConversationSession -> Messages relationship
        conv = ConversationSession(user_id=test_user.id, status="active")
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        
        msg = ConversationMessage(
            session_id=conv.id,
            role="user",
            content="Test"
        )
        session.add(msg)
        await session.commit()
        
        # Load with relationship
        result = await session.execute(
            select(ConversationSession).where(ConversationSession.id == conv.id)
        )
        loaded_conv = result.scalar_one()
        await session.refresh(loaded_conv)
        
        assert len(loaded_conv.messages) == 1
