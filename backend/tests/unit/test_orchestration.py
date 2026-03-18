"""Tests for orchestration layer."""
import asyncio
from datetime import datetime
from uuid import uuid4

import pytest

from app.orchestration.dispatcher.states import TaskState, TaskStateMachine
from app.orchestration.sandbox.instance import (
    ExecutionResult,
    LocalSandboxInstance,
    SecurityScanResult,
    SandboxStatus,
)
from app.orchestration.version.diff import DiffCalculator, DiffResult


class TestTaskStateMachine:
    """Tests for task state machine."""

    def test_valid_transition_pending_to_queued(self):
        """Test valid transition from pending to queued."""
        assert TaskStateMachine.can_transition(TaskState.PENDING, TaskState.QUEUED)

    def test_valid_transition_running_to_completed(self):
        """Test valid transition from running to completed."""
        assert TaskStateMachine.can_transition(TaskState.RUNNING, TaskState.VERIFYING)
        assert TaskStateMachine.can_transition(TaskState.VERIFYING, TaskState.COMPLETED)

    def test_invalid_transition_completed_to_running(self):
        """Test invalid transition from completed to running."""
        assert not TaskStateMachine.can_transition(TaskState.COMPLETED, TaskState.RUNNING)

    def test_terminal_states(self):
        """Test terminal states have no transitions."""
        assert TaskStateMachine.is_terminal(TaskState.COMPLETED)
        assert TaskStateMachine.is_terminal(TaskState.CANCELLED)
        assert not TaskStateMachine.is_terminal(TaskState.PENDING)

    def test_retryable_states(self):
        """Test retryable states."""
        assert TaskStateMachine.is_retryable(TaskState.FAILED)
        assert TaskStateMachine.is_retryable(TaskState.TIMEOUT)
        assert not TaskStateMachine.is_retryable(TaskState.COMPLETED)

    def test_transition_returns_new_state(self):
        """Test transition method returns correct state."""
        new_state = TaskStateMachine.transition(TaskState.PENDING, TaskState.QUEUED)
        assert new_state == TaskState.QUEUED

    def test_transition_returns_none_for_invalid(self):
        """Test transition returns None for invalid transition."""
        result = TaskStateMachine.transition(TaskState.COMPLETED, TaskState.RUNNING)
        assert result is None


class TestLocalSandboxInstance:
    """Tests for local sandbox instance."""

    @pytest.fixture
    def sandbox(self):
        """Create a sandbox instance."""
        return LocalSandboxInstance("test-sandbox", timeout_seconds=10)

    @pytest.mark.asyncio
    async def test_initialize(self, sandbox):
        """Test sandbox initialization."""
        await sandbox.initialize()
        assert sandbox.status == SandboxStatus.READY

    @pytest.mark.asyncio
    async def test_terminate(self, sandbox):
        """Test sandbox termination."""
        await sandbox.initialize()
        await sandbox.terminate()
        assert sandbox.status == SandboxStatus.TERMINATED

    @pytest.mark.asyncio
    async def test_execute_simple_code(self, sandbox):
        """Test executing simple code."""
        await sandbox.initialize()

        result = await sandbox.execute("print('Hello, World!')")

        assert result.success
        assert "Hello, World!" in result.output
        assert result.exit_code == 0

        await sandbox.terminate()

    @pytest.mark.asyncio
    async def test_execute_with_error(self, sandbox):
        """Test executing code with error."""
        await sandbox.initialize()

        result = await sandbox.execute("raise ValueError('test error')")

        assert not result.success
        assert "test error" in result.error

        await sandbox.terminate()

    @pytest.mark.asyncio
    async def test_security_scan_clean_code(self, sandbox):
        """Test security scan on clean code."""
        await sandbox.initialize()

        result = await sandbox.security_scan("x = 1 + 1")

        assert result.passed
        assert result.severity == "none"

        await sandbox.terminate()

    @pytest.mark.asyncio
    async def test_security_scan_dangerous_code(self, sandbox):
        """Test security scan on dangerous code."""
        await sandbox.initialize()

        result = await sandbox.security_scan("import os; os.system('rm -rf /')")

        assert not result.passed
        assert len(result.issues) > 0

        await sandbox.terminate()

    @pytest.mark.asyncio
    async def test_acquire_release(self, sandbox):
        """Test acquire and release."""
        await sandbox.initialize()

        await sandbox.acquire()
        assert sandbox.status == SandboxStatus.BUSY

        sandbox.release()
        assert sandbox.status == SandboxStatus.READY

        await sandbox.terminate()

    @pytest.mark.asyncio
    async def test_health_check(self, sandbox):
        """Test health check."""
        await sandbox.initialize()

        is_healthy = await sandbox.health_check()
        assert is_healthy

        await sandbox.terminate()


class TestDiffCalculator:
    """Tests for diff calculator."""

    def test_compute_hash(self):
        """Test hash computation."""
        content = b"test content"
        hash1 = DiffCalculator.compute_hash(content)
        hash2 = DiffCalculator.compute_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length

    def test_compare_trees_added(self):
        """Test comparing trees with added files."""
        old_tree = {"file1.txt": "hash1"}
        new_tree = {"file1.txt": "hash1", "file2.txt": "hash2"}

        result = DiffCalculator.compare_trees(old_tree, new_tree)

        assert len(result.added) == 1
        assert result.added[0].path == "file2.txt"
        assert len(result.modified) == 0
        assert len(result.deleted) == 0

    def test_compare_trees_deleted(self):
        """Test comparing trees with deleted files."""
        old_tree = {"file1.txt": "hash1", "file2.txt": "hash2"}
        new_tree = {"file1.txt": "hash1"}

        result = DiffCalculator.compare_trees(old_tree, new_tree)

        assert len(result.deleted) == 1
        assert result.deleted[0].path == "file2.txt"
        assert len(result.added) == 0
        assert len(result.modified) == 0

    def test_compare_trees_modified(self):
        """Test comparing trees with modified files."""
        old_tree = {"file1.txt": "hash1", "file2.txt": "hash2"}
        new_tree = {"file1.txt": "hash1", "file2.txt": "hash3"}

        result = DiffCalculator.compare_trees(old_tree, new_tree)

        assert len(result.modified) == 1
        assert result.modified[0].path == "file2.txt"
        assert result.modified[0].old_hash == "hash2"
        assert result.modified[0].new_hash == "hash3"

    def test_compare_trees_no_changes(self):
        """Test comparing identical trees."""
        tree = {"file1.txt": "hash1", "file2.txt": "hash2"}

        result = DiffCalculator.compare_trees(tree, tree)

        assert result.is_empty
        assert result.total_changes == 0

    def test_compute_tree_hash(self):
        """Test tree hash computation."""
        tree1 = {"a.txt": "hash1", "b.txt": "hash2"}
        tree2 = {"b.txt": "hash2", "a.txt": "hash1"}  # Same content, different order

        hash1 = DiffCalculator.compute_tree_hash(tree1)
        hash2 = DiffCalculator.compute_tree_hash(tree2)

        # Should be same regardless of key order
        assert hash1 == hash2

    def test_diff_result_to_dict(self):
        """Test diff result serialization."""
        result = DiffResult()
        result.added.append(
            type("DiffEntry", (), {"path": "new.txt", "new_hash": "h1"})()
        )

        d = result.to_dict()

        assert "added" in d
        assert "total_changes" in d
        assert d["total_changes"] == 1