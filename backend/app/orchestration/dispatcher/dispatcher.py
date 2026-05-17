"""Task dispatcher for scheduling and managing tasks."""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models.task import Task
from app.orchestration.dispatcher.states import TaskState, TaskStateMachine
from app.orchestration.messaging.publisher import EventType, get_event_publisher
from app.orchestration.sandbox.pool import SandboxPool, get_sandbox_pool
from app.agents.base import (
    RequirementSpec,
    TaskCard,
    TaskPriority as AgentTaskPriority,
    TaskType as AgentTaskType,
)
from app.generation.code_generator import generate_code_from_task

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
        publish_events: bool = False,
    ):
        self._session = session
        self._pool_size = pool_size
        self._default_timeout = default_timeout
        self._publish_events = publish_events
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

    async def execute_queued(self, task_id: UUID) -> bool:
        """Execute an already-queued task in the current event loop."""
        await self._remove_from_queue(task_id)
        await self._execute_task(task_id)
        return True

    async def submit_and_execute(
        self,
        task_id: UUID,
        priority: TaskPriority = TaskPriority.MEDIUM,
    ) -> bool:
        """Submit a task and execute it immediately in the current event loop.

        This gives API-created tasks a deterministic minimal lifecycle while the
        longer-lived queue worker remains available for future concurrent runners.
        """
        queued = await self.submit(task_id, priority)
        if not queued:
            return False

        await self.execute_queued(task_id)
        return True

    async def _remove_from_queue(self, task_id: UUID) -> None:
        """Remove a task id from all in-memory queues if present."""
        for priority, queue in self._queues.items():
            kept: list[UUID] = []
            while True:
                try:
                    queued_task_id = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if queued_task_id != task_id:
                    kept.append(queued_task_id)
            for queued_task_id in kept:
                await queue.put(queued_task_id)

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

        # Update to RUNNING only if the task is still queued. This prevents a
        # cancellation that lands after submission but before the background
        # worker starts from being overwritten by execution.
        if not await self._update_state(
            task_id,
            TaskState.RUNNING,
            expected_state=TaskState.QUEUED,
        ):
            logger.info(f"Task {task_id} is no longer queued; skipping execution")
            return
        await self._session.refresh(task)

        # Update progress
        if task_id in self._progress:
            self._progress[task_id].state = TaskState.RUNNING
            self._progress[task_id].started_at = datetime.utcnow()

        # Publish event
        if self._publish_events:
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

                # Move through verification before terminal completion so the
                # persisted state machine and frontend visualization observe the
                # full minimal lifecycle.
                await self._update_state(task_id, TaskState.VERIFYING)
                if task_id in self._progress:
                    self._progress[task_id].state = TaskState.VERIFYING
                    self._progress[task_id].progress_percent = 90

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

                try:
                    from app.api.v1.endpoints.websocket import get_connection_manager

                    await get_connection_manager().broadcast_task_completed(task_id, result_data)
                except Exception as e:
                    logger.warning(f"Failed to broadcast task completion: {e}")

                # Publish completion event
                if self._publish_events:
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
        # Persist error details before the terminal state broadcast so clients
        # that react to the event can immediately read the durable error.
        await self._session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(error_message="Task execution timed out")
        )
        await self._session.flush()
        await self._update_state(task_id, TaskState.TIMEOUT)

        # Update progress
        if task_id in self._progress:
            self._progress[task_id].state = TaskState.TIMEOUT

        # Publish event
        if self._publish_events:
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
        # Persist error details before the terminal state broadcast so clients
        # that react to the event can immediately read the durable error.
        await self._session.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(error_message=error, completed_at=datetime.utcnow())
        )
        await self._session.flush()
        await self._update_state(task_id, TaskState.FAILED)

        # Update progress
        if task_id in self._progress:
            self._progress[task_id].state = TaskState.FAILED

        try:
            from app.api.v1.endpoints.websocket import get_connection_manager

            await get_connection_manager().broadcast_task_failed(task_id, error)
        except Exception as e:
            logger.warning(f"Failed to broadcast task failure: {e}")

        # Publish event
        if self._publish_events:
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

    async def _update_state(
        self,
        task_id: UUID,
        new_state: TaskState,
        expected_state: TaskState | None = None,
    ) -> bool:
        """Persist a task state transition and then notify task subscribers."""
        values: dict[str, Any] = {"status": new_state.value}
        if new_state == TaskState.RUNNING:
            values["started_at"] = datetime.utcnow()

        statement = update(Task).where(Task.id == task_id)
        if expected_state is not None:
            statement = statement.where(Task.status == expected_state.value)

        result = await self._session.execute(statement.values(**values))
        await self._session.flush()
        if expected_state is not None and result.rowcount == 0:
            await self._session.rollback()
            return False

        await self._session.commit()

        try:
            from app.api.v1.endpoints.websocket import get_connection_manager

            await get_connection_manager().broadcast_task_status(
                task_id,
                new_state.value,
                message=f"Task is {new_state.value}",
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast task state: {e}")

        logger.debug(f"Task {task_id} state updated to {new_state.value}")
        return True

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

        try:
            from app.api.v1.endpoints.websocket import get_connection_manager

            await get_connection_manager().broadcast_task_progress(
                task_id,
                progress_percent,
                message=message,
                status=self._progress[task_id].state.value if task_id in self._progress else None,
            )
        except Exception as e:
            logger.warning(f"Failed to broadcast progress: {e}")

        # Publish progress event
        if self._publish_events:
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


# Dispatcher helpers

def _coerce_agent_task_type(value: object) -> AgentTaskType:
    """Map persisted task types to the agent TaskCard enum."""
    try:
        return AgentTaskType(str(value))
    except ValueError:
        return AgentTaskType.FEATURE


def _coerce_agent_priority(value: object) -> AgentTaskPriority:
    """Map persisted task priorities to the agent TaskCard enum."""
    try:
        return AgentTaskPriority(str(value))
    except ValueError:
        return AgentTaskPriority.MEDIUM


def _requirements_from_task(task: Task) -> list[RequirementSpec]:
    """Build generator RequirementSpec objects from persisted task metadata."""
    raw_requirements = task.structured_requirements or []
    if isinstance(raw_requirements, dict):
        raw_requirements = [raw_requirements]

    requirements: list[RequirementSpec] = []
    for raw in raw_requirements:
        if not isinstance(raw, dict):
            continue
        req_type = raw.get("type")
        name = raw.get("name") or raw.get("field")
        default_value = raw.get("default")
        if isinstance(default_value, dict) and "spec" in default_value:
            spec = default_value.get("spec") or {}
            constraints = default_value.get("constraints") or raw.get("constraints") or {}
        else:
            spec = raw.get("spec")
            constraints = raw.get("constraints") or {}
        if spec is None:
            spec = {key: value for key, value in raw.items() if key not in {"field", "name", "type", "constraints"}}
        if isinstance(req_type, str) and isinstance(name, str) and isinstance(spec, dict):
            requirements.append(
                RequirementSpec(
                    type=req_type,
                    name=name,
                    spec=spec,
                    constraints=constraints,
                )
            )
    return requirements


def _task_to_task_card(task: Task) -> TaskCard:
    """Convert a persisted Task into the generator-facing TaskCard."""
    constraints = task.constraints or {}
    return TaskCard(
        id=str(task.id),
        type=_coerce_agent_task_type(task.type),
        priority=_coerce_agent_priority(task.priority),
        description=task.description,
        requirements=_requirements_from_task(task),
        structured_requirements=task.structured_requirements or [],
        constraints=constraints,
        target_zone=constraints.get("target_zone", "mutable"),
        timeout_seconds=task.timeout_seconds or settings.sandbox_timeout_seconds,
        session_id=str(task.session_id) if task.session_id else None,
    )


def _verify_generated_files(files: list[Any]) -> dict[str, Any]:
    """Run deterministic in-process validation for generated code artifacts."""
    errors: list[str] = []
    checked_files: list[str] = []
    for generated_file in files:
        path = generated_file.path
        checked_files.append(path)
        if not generated_file.content.strip():
            errors.append(f"{path}: generated file is empty")
            continue
        if path.endswith(".py"):
            try:
                compile(generated_file.content, path, "exec")
            except SyntaxError as exc:
                errors.append(f"{path}: syntax error at line {exc.lineno}: {exc.msg}")

    return {
        "success": not errors,
        "checked_files": checked_files,
        "errors": errors,
    }


async def default_task_handler(task: Task, update_progress: Callable) -> dict[str, Any]:
    """Generate code artifacts for a task and verify the generated output.

    This keeps the executor side-effect free: generated files are returned in the
    task result for review/preview, but are not written into the project tree.
    """
    await update_progress(task.id, 25, "需求已接收，正在分析任务")
    task_card = _task_to_task_card(task)

    await update_progress(task.id, 50, "正在基于任务卡生成代码")
    generation_result = await generate_code_from_task(task_card)
    generated_files = [
        {
            "path": generated_file.path,
            "description": generated_file.description,
            "size": len(generated_file.content),
            "content": generated_file.content,
        }
        for generated_file in generation_result.files
    ]

    await update_progress(task.id, 80, "正在验证生成结果")
    verification = _verify_generated_files(generation_result.files)
    if not verification["success"]:
        raise RuntimeError("Generated code validation failed: " + "; ".join(verification["errors"]))

    await update_progress(task.id, 90, "生成结果验证完成")
    return {
        "success": True,
        "output": f"Generated {len(generated_files)} file(s) for: {task.description}",
        "generated_files": generated_files,
        "files_changed": [file["path"] for file in generated_files],
        "verification": verification,
        "metrics": {
            "executor": "code_generation_handler",
            "task_type": task.type,
            "generated_file_count": len(generated_files),
        },
    }


def _build_task_dispatcher(session: AsyncSession) -> TaskDispatcher:
    """Create a dispatcher bound to one short-lived database session."""
    dispatcher = TaskDispatcher(session)
    for task_type in ["feature", "bugfix", "refactor", "test", "doc"]:
        dispatcher.register_handler(task_type, default_task_handler)
    return dispatcher


def session_factory_from_session(
    session: AsyncSession,
) -> async_sessionmaker[AsyncSession]:
    """Create a fresh AsyncSession factory using the current session's engine."""
    if session.bind is None:
        raise RuntimeError("Cannot create task execution session without a DB bind")
    return async_sessionmaker(
        session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def execute_submitted_task(
    session_factory: async_sessionmaker[AsyncSession],
    task_id: UUID,
) -> None:
    """Execute an already queued task using a fresh database session."""
    async with session_factory() as session:
        dispatcher = await get_task_dispatcher(session)
        await dispatcher.execute_queued(task_id)
        await session.commit()


async def get_task_dispatcher(session: AsyncSession) -> TaskDispatcher:
    """Create a task dispatcher for a session."""
    return _build_task_dispatcher(session)
