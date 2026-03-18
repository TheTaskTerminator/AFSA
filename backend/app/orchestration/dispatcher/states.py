"""Task state machine and states."""
from enum import Enum
from typing import Optional


class TaskState(str, Enum):
    """Task states for the state machine."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class TaskStateMachine:
    """State machine for task lifecycle management."""

    # Valid state transitions
    TRANSITIONS = {
        TaskState.PENDING: {TaskState.QUEUED, TaskState.CANCELLED},
        TaskState.QUEUED: {TaskState.RUNNING, TaskState.CANCELLED, TaskState.TIMEOUT},
        TaskState.RUNNING: {
            TaskState.VERIFYING,
            TaskState.FAILED,
            TaskState.TIMEOUT,
            TaskState.CANCELLED,
        },
        TaskState.VERIFYING: {
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
        },
        TaskState.COMPLETED: set(),  # Terminal state
        TaskState.FAILED: {TaskState.PENDING},  # Can retry
        TaskState.TIMEOUT: {TaskState.PENDING},  # Can retry
        TaskState.CANCELLED: set(),  # Terminal state
    }

    @classmethod
    def can_transition(cls, from_state: TaskState, to_state: TaskState) -> bool:
        """Check if a transition is valid."""
        return to_state in cls.TRANSITIONS.get(from_state, set())

    @classmethod
    def transition(
        cls, from_state: TaskState, to_state: TaskState
    ) -> Optional[TaskState]:
        """Attempt to transition and return the new state.

        Returns None if transition is invalid.
        """
        if cls.can_transition(from_state, to_state):
            return to_state
        return None

    @classmethod
    def is_terminal(cls, state: TaskState) -> bool:
        """Check if a state is terminal (no further transitions)."""
        return len(cls.TRANSITIONS.get(state, set())) == 0

    @classmethod
    def is_retryable(cls, state: TaskState) -> bool:
        """Check if a task in this state can be retried."""
        return TaskState.PENDING in cls.TRANSITIONS.get(state, set())