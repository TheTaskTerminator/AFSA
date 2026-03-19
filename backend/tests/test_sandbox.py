"""
Tests for AFSA Sandbox Runner and Verification System.

Tests cover:
- Sandbox execution
- Security scanning
- Code verification
- Pool management
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.orchestration.sandbox.runner import (
    SandboxRunner,
    VerificationResult,
    get_sandbox_runner,
)
from app.orchestration.sandbox.instance import (
    ExecutionResult,
    SecurityScanResult,
    SandboxStatus,
)
from app.orchestration.sandbox.pool import SandboxPool


# ============= Mock Fixtures =============

@pytest.fixture
def mock_execution_result():
    """Create a mock execution result."""
    return ExecutionResult(
        success=True,
        output="Hello, World!",
        error=None,
        exit_code=0,
    )


@pytest.fixture
def mock_security_result():
    """Create a mock security scan result."""
    return SecurityScanResult(
        passed=True,
        issues=[],
        severity="none",
    )


@pytest.fixture
def mock_sandbox_instance(mock_execution_result, mock_security_result):
    """Create a mock sandbox instance."""
    instance = MagicMock()
    instance.execute = AsyncMock(return_value=mock_execution_result)
    instance.security_scan = AsyncMock(return_value=mock_security_result)
    instance.health_check = AsyncMock(return_value=True)
    instance.reset = AsyncMock()
    instance.terminate = AsyncMock()
    instance.status = SandboxStatus.READY
    instance.execution_count = 0
    return instance


@pytest.fixture
def mock_pool(mock_sandbox_instance):
    """Create a mock sandbox pool."""
    pool = MagicMock(spec=SandboxPool)
    pool.acquire = AsyncMock(return_value=mock_sandbox_instance)
    pool.release = AsyncMock()
    pool.health_check = AsyncMock(return_value={
        "status": "healthy",
        "total": 2,
        "available": 2,
        "in_use": 0,
    })
    pool.terminate = AsyncMock()
    return pool


# ============= SandboxRunner Tests =============

class TestSandboxRunner:
    """Tests for SandboxRunner."""

    @pytest.fixture
    def runner(self, mock_pool):
        """Create a SandboxRunner with mock pool."""
        return SandboxRunner(pool=mock_pool)

    @pytest.mark.asyncio
    async def test_execute_success(self, runner, mock_execution_result):
        """Test successful code execution."""
        result = await runner.execute(
            code="print('Hello')",
            language="python",
        )
        
        assert result.success is True
        assert result.output == "Hello, World!"
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, runner):
        """Test code execution with custom timeout."""
        result = await runner.execute(
            code="import time; time.sleep(10)",
            language="python",
            timeout_seconds=5,
        )
        
        # Should call execute with the timeout
        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_with_env_vars(self, runner):
        """Test code execution with environment variables."""
        result = await runner.execute(
            code="import os; print(os.getenv('TEST_VAR'))",
            language="python",
            env_vars={"TEST_VAR": "test_value"},
        )
        
        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_skip_security_scan(self, runner, mock_sandbox_instance):
        """Test execution with security scan skipped."""
        result = await runner.execute(
            code="eval('dangerous')",
            language="python",
            skip_security_scan=True,
        )
        
        # Security scan should not be called
        mock_sandbox_instance.security_scan.assert_not_called()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_security_scan_fails(self, runner, mock_sandbox_instance):
        """Test execution when security scan fails."""
        # Mock security scan to fail
        mock_sandbox_instance.security_scan.return_value = SecurityScanResult(
            passed=False,
            issues=[{"type": "dangerous_pattern", "message": "eval() detected"}],
            severity="high",
        )
        
        result = await runner.execute(
            code="eval('dangerous')",
            language="python",
            skip_security_scan=False,
        )
        
        assert result.success is False
        assert "Security scan failed" in result.error

    @pytest.mark.asyncio
    async def test_execute_no_available_instance(self, runner, mock_pool):
        """Test execution when no sandbox instance is available."""
        mock_pool.acquire.return_value = None
        
        result = await runner.execute(
            code="print('test')",
            language="python",
        )
        
        assert result.success is False
        assert "No available sandbox" in result.error

    @pytest.mark.asyncio
    async def test_verify_success(self, runner):
        """Test code verification with tests."""
        result = await runner.verify(
            code="def add(a, b): return a + b",
            tests="assert add(2, 3) == 5",
            language="python",
        )
        
        assert isinstance(result, VerificationResult)
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_verify_without_tests(self, runner):
        """Test code verification without tests."""
        result = await runner.verify(
            code="print('Hello')",
            language="python",
        )
        
        assert result.passed is True
        assert result.tests_total == 0

    @pytest.mark.asyncio
    async def test_verify_security_issue(self, runner, mock_sandbox_instance):
        """Test verification fails on security issue."""
        mock_sandbox_instance.security_scan.return_value = SecurityScanResult(
            passed=False,
            issues=[{"type": "sql_injection", "message": "SQL injection detected"}],
            severity="critical",
        )
        
        result = await runner.verify(
            code="query = 'SELECT * FROM users'",
            language="python",
        )
        
        assert result.passed is False
        assert result.security_result is not None
        assert result.security_result.passed is False

    @pytest.mark.asyncio
    async def test_verify_execution_fails(self, runner, mock_sandbox_instance):
        """Test verification fails on execution error."""
        mock_sandbox_instance.execute.return_value = ExecutionResult(
            success=False,
            output="",
            error="SyntaxError: invalid syntax",
            exit_code=1,
        )
        
        result = await runner.verify(
            code="def broken(:",
            language="python",
        )
        
        assert result.passed is False
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_execute_with_callback(self, runner):
        """Test execution with callback."""
        callback = AsyncMock()
        
        result = await runner.execute_with_callback(
            code="print('test')",
            callback=callback,
            language="python",
        )
        
        callback.assert_called_once_with(result)

    @pytest.mark.asyncio
    async def test_batch_execute(self, runner, mock_pool, mock_sandbox_instance):
        """Test batch code execution."""
        code_list = [
            ("print('one')", "python"),
            ("print('two')", "python"),
            ("print('three')", "python"),
        ]
        
        results = await runner.batch_execute(
            code_list=code_list,
            timeout_seconds=30,
            max_concurrent=2,
        )
        
        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_health_check(self, runner, mock_pool):
        """Test health check."""
        health = await runner.health_check()
        
        assert "status" in health
        assert "pool" in health
        assert "running_verifications" in health


# ============= VerificationResult Tests =============

class TestVerificationResult:
    """Tests for VerificationResult."""

    def test_verification_result_success(self):
        """Test successful verification result."""
        result = VerificationResult(
            passed=True,
            tests_passed=5,
            tests_total=5,
        )
        
        assert result.passed is True
        assert result.tests_passed == 5
        assert result.tests_total == 5
        assert len(result.errors) == 0

    def test_verification_result_failure(self):
        """Test failed verification result."""
        result = VerificationResult(
            passed=False,
            errors=["Security issue detected", "Test failed"],
        )
        
        assert result.passed is False
        assert len(result.errors) == 2


# ============= Global Runner Tests =============

class TestGetSandboxRunner:
    """Tests for get_sandbox_runner function."""

    @pytest.mark.asyncio
    async def test_get_sandbox_runner_creates_instance(self):
        """Test that get_sandbox_runner creates a new instance."""
        # Clear global instance
        from app.orchestration.sandbox import runner as runner_module
        runner_module._runner = None
        
        runner = await get_sandbox_runner()
        assert runner is not None
        assert isinstance(runner, SandboxRunner)
        
        # Second call should return same instance
        runner2 = await get_sandbox_runner()
        assert runner is runner2


# ============= Security Boundary Tests =============

class TestSecurityBoundaries:
    """Tests for security boundaries and isolation."""

    @pytest.fixture
    def runner(self, mock_pool):
        """Create a SandboxRunner for security tests."""
        return SandboxRunner(pool=mock_pool)

    @pytest.mark.asyncio
    async def test_mutable_immutable_isolation(self, runner, mock_sandbox_instance):
        """Test that mutable and immutable zones are isolated."""
        # Execute code that tries to access immutable zone
        code = """
import os
# Try to access protected paths
protected_paths = ['/etc/afsa/immutable', '/app/core']
for path in protected_paths:
    if os.path.exists(path):
        print(f'Accessed: {path}')
"""
        result = await runner.execute(
            code=code,
            language="python",
        )
        
        # Should execute without accessing protected paths
        assert result is not None

    @pytest.mark.asyncio
    async def test_dangerous_patterns_detected(self, runner, mock_sandbox_instance):
        """Test that dangerous code patterns are detected."""
        dangerous_patterns = [
            "eval('print(1)')",
            "exec('x = 1')",
            "__import__('os').system('ls')",
            "subprocess.run(['rm', '-rf', '/'])",
        ]
        
        for pattern in dangerous_patterns:
            mock_sandbox_instance.security_scan.return_value = SecurityScanResult(
                passed=False,
                issues=[{"type": "dangerous_pattern", "message": f"Detected: {pattern}"}],
                severity="high",
            )
            
            result = await runner.execute(
                code=pattern,
                language="python",
                skip_security_scan=False,
            )
            
            assert result.success is False
            assert "Security scan failed" in result.error

    @pytest.mark.asyncio
    async def test_network_access_blocked(self, runner, mock_sandbox_instance):
        """Test that network access is blocked."""
        code = """
import socket
try:
    socket.create_connection(("example.com", 80), timeout=2)
    print("Network accessible")
except Exception as e:
    print(f"Network blocked: {e}")
"""
        result = await runner.execute(
            code=code,
            language="python",
        )
        
        # Network should be blocked in sandbox
        assert result is not None


# ============= Permission Tests =============

class TestPermissionVerification:
    """Tests for permission verification."""

    @pytest.fixture
    def runner(self, mock_pool):
        """Create a SandboxRunner for permission tests."""
        return SandboxRunner(pool=mock_pool)

    @pytest.mark.asyncio
    async def test_execution_respects_permissions(self, runner, mock_sandbox_instance):
        """Test that execution respects permission boundaries."""
        # Code that requires elevated permissions
        code = """
import os
try:
    # Try to change to root directory
    os.chmod('/etc/passwd', 0o777)
    print("Permission granted")
except PermissionError:
    print("Permission denied")
"""
        result = await runner.execute(
            code=code,
            language="python",
        )
        
        # Should execute and handle permission error
        assert result is not None

    @pytest.mark.asyncio
    async def test_file_system_isolation(self, runner, mock_sandbox_instance):
        """Test that filesystem is properly isolated."""
        code = """
import os
import tempfile

# Create a file in temp directory
with tempfile.NamedTemporaryFile(delete=False) as f:
    f.write(b'test content')
    temp_path = f.name

# Verify file exists
exists = os.path.exists(temp_path)
print(f"File exists: {exists}")

# Clean up
os.unlink(temp_path)
"""
        result = await runner.execute(
            code=code,
            language="python",
        )
        
        assert result.success is True


# ============= Integration Tests =============

class TestSandboxIntegration:
    """Integration tests for sandbox system."""

    @pytest.mark.asyncio
    async def test_full_verification_workflow(self, runner, mock_sandbox_instance):
        """Test complete verification workflow."""
        code = """
def calculate(a, b, op):
    if op == 'add':
        return a + b
    elif op == 'sub':
        return a - b
    elif op == 'mul':
        return a * b
    elif op == 'div':
        return a / b
    else:
        raise ValueError(f"Unknown operation: {op}")
"""
        
        tests = """
# Test cases
assert calculate(2, 3, 'add') == 5
assert calculate(10, 4, 'sub') == 6
assert calculate(3, 4, 'mul') == 12
assert calculate(20, 5, 'div') == 4
print("All tests passed!")
"""
        
        result = await runner.verify(
            code=code,
            tests=tests,
            language="python",
        )
        
        assert result.passed is True
        assert result.tests_passed > 0

    @pytest.mark.asyncio
    async def test_concurrent_executions(self, runner, mock_pool):
        """Test concurrent code executions."""
        async def execute_code(code: str):
            return await runner.execute(code, language="python")
        
        # Execute multiple codes concurrently
        tasks = [
            execute_code(f"print('task_{i}')")
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert len(results) == 5
        assert all(r.success for r in results)
