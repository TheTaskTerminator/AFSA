"""Task management endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.task import Task
from app.repositories.task import TaskRepository
from app.schemas.task import (
    TaskCreate,
    TaskPriority,
    TaskRead,
    TaskStatus,
    TaskUpdate,
)
from app.orchestration.dispatcher.dispatcher import get_task_dispatcher

router = APIRouter()


def _task_to_read(task: Task) -> TaskRead:
    """Convert Task model to TaskRead schema."""
    return TaskRead.model_validate(task)


async def get_task_repo(db: AsyncSession = Depends(get_db)) -> TaskRepository:
    """Get task repository dependency."""
    return TaskRepository(db)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    task: TaskCreate,
    repo: TaskRepository = Depends(get_task_repo),
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    """Create a new task.

    Creates a task and optionally submits it to the dispatcher for execution.
    """
    # Create task in database
    db_task = await repo.create(task)
    await db.commit()
    await db.refresh(db_task)

    # If task has session_id, optionally submit to dispatcher
    # This is done separately to allow for manual submission
    if task.session_id:
        try:
            dispatcher = await get_task_dispatcher(db)
            priority = TaskPriority(task.priority.value) if task.priority else TaskPriority.MEDIUM
            await dispatcher.submit(db_task.id, priority)
            await db.commit()
            await db.refresh(db_task)
        except Exception:
            # Log but don't fail creation if dispatcher fails
            pass

    return _task_to_read(db_task)


@router.get("", response_model=List[TaskRead])
async def list_tasks(
    status: Optional[TaskStatus] = Query(None, description="Filter by task status"),
    priority: Optional[TaskPriority] = Query(None, description="Filter by task priority"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    session_id: Optional[UUID] = Query(None, description="Filter by conversation session ID"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of tasks to return"),
    offset: int = Query(0, ge=0, description="Number of tasks to skip"),
    repo: TaskRepository = Depends(get_task_repo),
) -> List[TaskRead]:
    """List tasks with optional filtering.

    Supports filtering by status, priority, user, and session.
    Results are paginated and ordered by creation date (newest first).
    """
    tasks = []

    if status:
        tasks = await repo.get_by_status(status.value, skip=offset, limit=limit)
    elif user_id:
        tasks = await repo.get_by_user(user_id, skip=offset, limit=limit)
    elif session_id:
        tasks = await repo.get_by_session(session_id, skip=offset, limit=limit)
    else:
        from sqlalchemy import desc
        tasks = await repo.get_all(skip=offset, limit=limit, order_by=desc(Task.created_at))

    # Filter by priority if specified (additional filter)
    if priority and tasks:
        tasks = [t for t in tasks if t.priority == priority.value]

    return [_task_to_read(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: UUID,
    repo: TaskRepository = Depends(get_task_repo),
) -> TaskRead:
    """Get task by ID.

    Returns the task details including status, result, and metadata.
    """
    task = await repo.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )
    return _task_to_read(task)


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: UUID,
    task_update: TaskUpdate,
    repo: TaskRepository = Depends(get_task_repo),
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    """Update task properties.

    Allows updating priority and status (for manual status changes).
    """
    task = await repo.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    # Update allowed fields
    update_data = task_update.model_dump(exclude_unset=True)
    if update_data:
        for key, value in update_data.items():
            if hasattr(task, key) and value is not None:
                setattr(task, key, value)
        await db.commit()
        await db.refresh(task)

    return _task_to_read(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_task(
    task_id: UUID,
    repo: TaskRepository = Depends(get_task_repo),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Cancel a task.

    Cancels a task if it's in pending or queued state.
    Running tasks cannot be cancelled through this endpoint.
    """
    task = await repo.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    # Check if task can be cancelled
    if task.status not in [TaskStatus.PENDING.value, TaskStatus.QUEUED.value]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel task in status: {task.status}",
        )

    # Cancel via repository
    cancelled_task = await repo.cancel(task_id)
    if cancelled_task is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel task",
        )

    await db.commit()


@router.post("/{task_id}/submit", response_model=TaskRead)
async def submit_task(
    task_id: UUID,
    repo: TaskRepository = Depends(get_task_repo),
    db: AsyncSession = Depends(get_db),
) -> TaskRead:
    """Submit a task for execution.

    Queues the task in the dispatcher for execution.
    Task must be in pending state.
    """
    task = await repo.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    if task.status != TaskStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task must be in pending status to submit. Current status: {task.status}",
        )

    # Submit to dispatcher
    dispatcher = await get_task_dispatcher(db)
    priority = TaskPriority(task.priority) if task.priority else TaskPriority.MEDIUM
    success = await dispatcher.submit(task_id, priority)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit task to dispatcher",
        )

    await db.commit()
    await db.refresh(task)

    return _task_to_read(task)


@router.get("/{task_id}/progress")
async def get_task_progress(
    task_id: UUID,
    repo: TaskRepository = Depends(get_task_repo),
    db: AsyncSession = Depends(get_db),
):
    """Get task execution progress.

    Returns current progress information including percentage and message.
    """
    task = await repo.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}",
        )

    # Get progress from dispatcher
    dispatcher = await get_task_dispatcher(db)
    progress = dispatcher.get_progress(task_id)

    if progress:
        return {
            "task_id": str(task_id),
            "status": task.status,
            "progress_percent": progress.progress_percent,
            "message": progress.message,
            "started_at": progress.started_at.isoformat() if progress.started_at else None,
            "completed_at": progress.completed_at.isoformat() if progress.completed_at else None,
        }

    # Return basic progress from task status
    progress_percent = 0
    if task.status == TaskStatus.COMPLETED.value:
        progress_percent = 100
    elif task.status == TaskStatus.RUNNING.value:
        progress_percent = 50
    elif task.status == TaskStatus.QUEUED.value:
        progress_percent = 10

    return {
        "task_id": str(task_id),
        "status": task.status,
        "progress_percent": progress_percent,
        "message": "",
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }