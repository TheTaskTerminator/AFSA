"""Task repository."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.repositories.base import BaseRepository
from app.schemas.task import TaskCreate, TaskUpdate


class TaskRepository(BaseRepository[Task, TaskCreate, TaskUpdate]):
    """Task repository for database operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Task, session)

    async def get_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[Task]:
        """Get tasks by status."""
        result = await self.session.execute(
            select(Task)
            .where(Task.status == status)
            .order_by(Task.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_user(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Task]:
        """Get tasks by user."""
        result = await self.session.execute(
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(Task.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_session(
        self, session_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Task]:
        """Get tasks by conversation session."""
        result = await self.session.execute(
            select(Task)
            .where(Task.session_id == session_id)
            .order_by(Task.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_pending_tasks(self, limit: int = 100) -> List[Task]:
        """Get all pending tasks ordered by priority and created_at."""
        priority_order = {"high": 0, "medium": 1, "low": 2}
        result = await self.session.execute(
            select(Task)
            .where(Task.status == "pending")
            .order_by(Task.created_at.asc())
            .limit(limit)
        )
        tasks = list(result.scalars().all())
        # Sort by priority
        tasks.sort(key=lambda t: priority_order.get(t.priority, 1))
        return tasks

    async def update_status(
        self,
        task_id: UUID,
        status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> Optional[Task]:
        """Update task status."""
        task = await self.get(task_id)
        if task is None:
            return None
        task.status = status
        if started_at is not None:
            task.started_at = started_at
        if completed_at is not None:
            task.completed_at = completed_at
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def set_result(
        self, task_id: UUID, result: dict, error_message: Optional[str] = None
    ) -> Optional[Task]:
        """Set task result."""
        task = await self.get(task_id)
        if task is None:
            return None
        task.result = result
        task.error_message = error_message
        task.completed_at = datetime.utcnow()
        task.status = "completed" if error_message is None else "failed"
        await self.session.flush()
        await self.session.refresh(task)
        return task

    async def cancel(self, task_id: UUID) -> Optional[Task]:
        """Cancel a task."""
        task = await self.get(task_id)
        if task is None:
            return None
        if task.status in ["pending", "queued"]:
            task.status = "cancelled"
            await self.session.flush()
            await self.session.refresh(task)
        return task

    async def get_running_tasks(self, limit: int = 100) -> List[Task]:
        """Get all running tasks."""
        result = await self.session.execute(
            select(Task)
            .where(Task.status == "running")
            .order_by(Task.started_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())