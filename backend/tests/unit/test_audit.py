"""Tests for audit service."""
import pytest
from datetime import datetime, timedelta
from uuid import UUID

from app.governance.audit import AuditService
from app.schemas.audit import AuditResult


class TestAuditService:
    """Tests for AuditService."""

    @pytest.mark.asyncio
    async def test_log_success(self, session, test_user):
        """Test logging successful action."""
        service = AuditService(session)
        log = await service.log_success(
            action="task.create",
            resource="task",
            actor_user_id=test_user.id,
            actor_username=test_user.username,
            actor_role=test_user.role,
        )

        assert log.id is not None
        assert log.action == "task.create"
        assert log.resource == "task"
        assert log.result == "success"

    @pytest.mark.asyncio
    async def test_log_failure(self, session, test_user):
        """Test logging failed action."""
        service = AuditService(session)
        log = await service.log_failure(
            action="task.delete",
            resource="task",
            error_message="Task not found",
            actor_user_id=test_user.id,
        )

        assert log.id is not None
        assert log.result == "failure"
        assert log.error_message == "Task not found"

    @pytest.mark.asyncio
    async def test_log_with_changes(self, session, test_user):
        """Test logging with changes field."""
        service = AuditService(session)
        log = await service.log_success(
            action="task.update",
            resource="task",
            actor_user_id=test_user.id,
            changes={"status": {"from": "pending", "to": "running"}},
        )

        assert log.changes is not None
        assert log.changes["status"]["from"] == "pending"
        assert log.changes["status"]["to"] == "running"

    @pytest.mark.asyncio
    async def test_get_logs(self, session, test_user):
        """Test querying audit logs."""
        service = AuditService(session)

        # Create some logs
        await service.log_success("task.create", "task", actor_user_id=test_user.id)
        await service.log_success("task.update", "task", actor_user_id=test_user.id)
        await service.log_failure("task.delete", "task", "Not allowed", actor_user_id=test_user.id)

        # Query all logs
        logs = await service.get_logs()
        assert len(logs) == 3

        # Query by action
        logs = await service.get_logs(action="task.create")
        assert len(logs) == 1

        # Query by result
        logs = await service.get_logs(result="failure")
        assert len(logs) == 1

    @pytest.mark.asyncio
    async def test_get_logs_by_time_range(self, session, test_user):
        """Test querying logs by time range."""
        service = AuditService(session)

        # Create logs
        await service.log_success("action1", "resource1", actor_user_id=test_user.id)
        await service.log_success("action2", "resource2", actor_user_id=test_user.id)

        # Query with time range
        start = datetime.utcnow() - timedelta(hours=1)
        end = datetime.utcnow() + timedelta(hours=1)
        logs = await service.get_logs(start_time=start, end_time=end)

        assert len(logs) == 2

    @pytest.mark.asyncio
    async def test_count_logs(self, session, test_user):
        """Test counting audit logs."""
        service = AuditService(session)

        # Create some logs
        await service.log_success("task.create", "task", actor_user_id=test_user.id)
        await service.log_success("task.update", "task", actor_user_id=test_user.id)
        await service.log_failure("task.delete", "task", "Error", actor_user_id=test_user.id)

        # Count all
        count = await service.count_logs()
        assert count == 3

        # Count by action
        count = await service.count_logs(action="task.create")
        assert count == 1