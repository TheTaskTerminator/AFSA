"""Task dispatcher for scheduling and managing tasks."""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.task import Task
from app.orchestration.dispatcher.states import TaskState, TaskStateMachine
from app.orchestration.messaging.publisher import EventType, get_event_publisher
from app.orchestration.sandbox.pool import SandboxPool, get_sandbox_pool

logger = logging.getLogger(__name__)


class TaskPriority(str, Enum):
    """Task priority levels."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TaskProgress:
    """Progress information for a task."""

    task_id: UUID
    state: TaskState
    progress_percent: int = 0
    message: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskDispatcher:
    """Dispatcher for task scheduling and execution.

    Features:
    - Priority-based queue (HIGH > MEDIUM > LOW)
    - State machine for task lifecycle
    - Timeout handling
    - WebSocket progress notifications via events
    """

    def __init__(
        self,
        session: AsyncSession,
        pool_size: int = settings.sandbox_pool_size,
        default_timeout: int = settings.sandbox_timeout_seconds,
    ):
        self._session = session
        self._pool_size = pool_size
        self._default_timeout = default_timeout
        self._queues: dict[TaskPriority, asyncio.Queue] = {
            TaskPriority.HIGH: asyncio.Queue(),
            TaskPriority.MEDIUM: asyncio.Queue(),
            TaskPriority.LOW: asyncio.Queue(),
        }
        self._running_tasks: dict[UUID, asyncio.Task] = {}
        self._progress: dict[UUID, TaskProgress] = {}
        self._handlers: dict[str, Callable] = {}
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    def register_handler(
        self,
        task_type: str,
        handler: Callable,
    ) -> None:
        """Register a handler for a task type.

        Args:
            task_type: Type of task (e.g., 'feature', 'bugfix')
            handler: Async function to handle the task
        """
        self._handlers[task_type] = handler
        logger.info(f"Registered handler for task type: {task_type}")

    async def start(self) -> None:
        """Start the dispatcher worker."""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Task dispatcher started")

    async def stop(self) -> None:
        """Stop the dispatcher worker."""
        self._running = False

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        # Cancel all running tasks
        for task in self._running_tasks.values():
            task.cancel()

        self._running_tasks.clear()
        logger.info("Task dispatcher stopped")

    async def submit(
        self,
        task_id: UUID,
        priority: TaskPriority = TaskPriority.MEDIUM,
    ) -> bool:
        """Submit a task for execution.

        Args:
            task_id: Task UUID
            priority: Task priority level

        Returns:
            True if successfully queued.
        """
        # Get task from database
        result = await self._session.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            logger.error(f"Task not found: {task_id}")
            return False

        # Check if task can be queued
        current_state = TaskState(task.status)
        if not TaskStateMachine.can_transition(current_state, TaskState.QUEUED):
            logger.warning(f"Task {task_id} cannot be queued from state {current_state}")
            return False

        # Update state to QUEUED
        await self._update_state(task_id, TaskState.QUEUED)

        # Add to appropriate queue
        await self._queues[priority].put(task_id)

        # Initialize progress
        self._progress[task_id] = TaskProgress(
            task_id=task_id,
            state=TaskState.QUEUED,
        )

        logger.info(f"Task {task_id} queued with priority {priority.value}")
        return True

    async def cancel(self, task_id: UUID) -> bool:
        """Cancel a task.

        Args:
            task_id: Task UUID

        Returns:
            True if successfully cancelled.
        """
        # Cancel running task if exists
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
            del self._running_tasks[task_id]

        # Update state
        await self._update_state(task_id, TaskState.CANCELLED)

        # Update progress
        if task_id in self._progress:
            self._progress[task_id].state = TaskState.CANCELLED

        logger.info(f"Task {task_id} cancelled")
        return True

    def get_progress(self, task_id: UUID) -> Optional[TaskProgress]:
        """Get progress for a task."""
        return self._progress.get(task_id)

    async def _worker_loop(self) -> None:
        """Main worker loop for processing tasks."""
        while self._running:
            try:
                # Check queues in priority order
                task_id = None
                for priority in [TaskPriority.HIGH, TaskPriority.MEDIUM, TaskPriority.LOW]:
                    try:
                        task_id = self._queues[priority].get_nowait()
                        break
                    except asyncio.QueueEmpty:
                        continue

                if task_id:
                    # Execute task
                    asyncio.create_task(self._execute_task(task_id))
                else:
                    # No tasks, wait a bit
                    await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(1)

    async def _execute_task(self, task_id: UUID) -> None:
        """Execute a single task."""
        # Get task
        result = await self._session.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            logger.error(f"Task not found: {task_id}")
            return

        # Update to RUNNING
        await self._update_state(task_id, TaskState.RUNNING)

        # Update progress
        if task_id in self._progress:
            self._progress[task_id].state = TaskState.RUNNING
            self._progress[task_id].started_at = datetime.utcnow()

        # Publish event
        try:
            publisher = await get_event_publisher()
            await publisher.publish_task_event(
                EventType.TASK_STARTED,
                task_id,
                type=task.type,
            )
        except Exception as e:
            logger.warning(f"Failed to publish event: {e}")

        try:
            # Get handler
            handler = self._handlers.get(task.type)
            if not handler:
                raise ValueError(f"No handler registered for task type: {task.type}")

            # Create execution task with timeout
            timeout = task.timeout_seconds or self._default_timeout
            execution_task = asyncio.create_task(handler(task, self._update_progress))
            self._running_tasks[task_id] = execution_task

            # Wait with timeout
            try:
                result_data = await asyncio.wait_for(execution_task, timeout=timeout)

                # Update task result
                await self._session.execute(
                    update(Task)
                    .where(Task.id == task_id)
                    .values(result=result_data, completed_at=datetime.utcnow())
                )
                await self._session.flush()

                # Update state to COMPLETED
                await self._update_state(task_id, TaskState.COMPLETED)

                # Update progress
                if task_id in self._progress:
                    self._progress[task_id].state = TaskState.COMPLETED
                    self._progress[task_id].progress_percent = 100
                    self._progress[task_id].completed_at = datetime.utcnow()

                # Publish completion event
                try:
                    publisher = await get_event_publisher()
                    await publisher.publish_task_event(
                        EventType.TASK_COMPLETED,
                        task_id,
                        result=result_data,
                    )
                except Exception as e:
                    logger.warning(f"Failed to publish event: {e}")

                logger.info(f"Task {task_id} completed successfully")

            except asyncio.TimeoutError:
                await self._handle_timeout(task_id)

        except asyncio.CancelledError:
            await self._update_state(task_id, TaskState.CANCELLED)
            logger.info(f"Task {task_id} was cancelled")

        except Exception as e:
            await self._handle_failure(task_id, str(e))

        finally:
            # Cleanup
            if task_id in self._running_tasks:
                del self._running_tasks[task_id]

    async def _handle_timeout(self, task_id: UUID) -> None:
        """Handle task timeout."""
        await self._update_state(task_id, TaskState.TIMEOUT)

        # Update error message
        await self._session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(error_message="Task execution timed out")
        )
        await self._session.flush()

        # Update progress
        if task_id in self._progress:
            self._progress[task_id].state = TaskState.TIMEOUT

        # Publish event
        try:
            publisher = await get_event_publisher()
            await publisher.publish_task_event(
                EventType.TASK_TIMEOUT,
                task_id,
            )
        except Exception as e:
            logger.warning(f"Failed to publish event: {e}")

        logger.warning(f"Task {task_id} timed out")

    async def _handle_failure(self, task_id: UUID, error: str) -> None:
        """Handle task failure."""
        await self._update_state(task_id, TaskState.FAILED)

        # Update error message
        await self._session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(error_message=error, completed_at=datetime.utcnow())
        )
        await self._session.flush()

        # Update progress
        if task_id in self._progress:
            self._progress[task_id].state = TaskState.FAILED

        # Publish event
        try:
            publisher = await get_event_publisher()
            await publisher.publish_task_event(
                EventType.TASK_FAILED,
                task_id,
                error=error,
            )
        except Exception as e:
            logger.warning(f"Failed to publish event: {e}")

        logger.error(f"Task {task_id} failed: {error}")

    async def _update_state(self, task_id: UUID, new_state: TaskState) -> None:
        """Update task state in database."""
        await self._session.execute(
            update(Task).where(Task.id == task_id).values(status=new_state.value)
        )
        await self._session.flush()
        logger.debug(f"Task {task_id} state updated to {new_state.value}")

    async def _update_progress(
        self,
        task_id: UUID,
        progress_percent: int,
        message: str = "",
    ) -> None:
        """Update task progress."""
        if task_id in self._progress:
            self._progress[task_id].progress_percent = progress_percent
            self._progress[task_id].message = message

        # Publish progress event
        try:
            publisher = await get_event_publisher()
            await publisher.publish_task_event(
                EventType.TASK_PROGRESS,
                task_id,
                progress_percent=progress_percent,
                message=message,
            )
        except Exception as e:
            logger.warning(f"Failed to publish progress: {e}")


# Global dispatcher factory
_dispatchers: dict[str, TaskDispatcher] = {}


async def get_task_dispatcher(session: AsyncSession) -> TaskDispatcher:
    """Get or create a task dispatcher for a session."""
    session_id = str(id(session))
    if session_id not in _dispatchers:
        _dispatchers[session_id] = TaskDispatcher(session)
        await _dispatchers[session_id].start()
    return _dispatchers[session_id]