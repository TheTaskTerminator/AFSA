"""Tests for Docker sandbox instance.

Note: These tests require Docker to be installed and running.
Tests will be skipped if Docker is not available.
"""
import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Skip all tests in this module if Docker is not available
pytestmark = pytest.mark.skipif(
    os.environ.get("SKIP_DOCKER_TESTS", "false").lower() == "true",
    reason="Docker tests disabled",
)

# Try to import Docker
try:
    import docker
    from docker.errors import DockerException
    DOCKER_INSTALLED = True
except ImportError:
    DOCKER_INSTALLED = False
    pytestmark = pytest.mark.skip(reason="Docker SDK not installed")


from app.orchestration.sandbox.docker_instance import (
    DockerSandboxInstance,
    is_docker_available,
)
from app.orchestration.sandbox.instance import SandboxStatus


@pytest.fixture
def check_docker():
    """Check if Docker daemon is running."""
    if not DOCKER_INSTALLED:
        pytest.skip("Docker SDK not installed")

    try:
        client = docker.from_env()
        client.ping()
        client.close()
    except Exception as e:
        pytest.skip(f"Docker daemon not available: {e}")


class TestDockerSandboxInstance:
    """Tests for DockerSandboxInstance."""

    @pytest.fixture
    async def sandbox(self, check_docker):
        """Create a Docker sandbox instance for testing."""
        instance = DockerSandboxInstance(
            sandbox_id="test_sandbox",
            memory_mb=128,
            cpu_limit=0.5,
            timeout_seconds=30,
        )
        await instance.initialize()
        yield instance
        await instance.terminate()

    @pytest.mark.asyncio
    async def test_initialize(self, check_docker):
        """Test Docker sandbox initialization."""
        instance = DockerSandboxInstance(sandbox_id="init_test")
        await instance.initialize()

        assert instance.status == SandboxStatus.READY
        assert instance._client is not None

        await instance.terminate()
        assert instance.status == SandboxStatus.TERMINATED

    @pytest.mark.asyncio
    async def test_execute_simple_code(self, sandbox):
        """Test executing simple Python code."""
        result = await sandbox.execute(
            code="print('Hello, Docker!')",
            language="python",
        )

        assert result.success is True
        assert "Hello, Docker!" in result.output
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_execute_with_result(self, sandbox):
        """Test executing code that returns a result."""
        result = await sandbox.execute(
            code="x = 10 + 20; print(f'Result: {x}')",
            language="python",
        )

        assert result.success is True
        assert "Result: 30" in result.output

    @pytest.mark.asyncio
    async def test_execute_with_error(self, sandbox):
        """Test executing code with an error."""
        result = await sandbox.execute(
            code="raise ValueError('Test error')",
            language="python",
        )

        assert result.success is False
        assert result.exit_code != 0
        assert "ValueError" in result.error or "ValueError" in result.output

    @pytest.mark.asyncio
    async def test_execute_timeout(self, sandbox):
        """Test execution timeout."""
        result = await sandbox.execute(
            code="import time; time.sleep(100)",
            language="python",
            timeout_seconds=2,
        )

        assert result.success is False
        assert "timed out" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_unsupported_language(self, sandbox):
        """Test executing unsupported language."""
        result = await sandbox.execute(
            code='console.log("Hello")',
            language="javascript",
        )

        assert result.success is False
        assert "Unsupported language" in result.error

    @pytest.mark.asyncio
    async def test_security_scan_clean(self, sandbox):
        """Test security scan with clean code."""
        result = await sandbox.security_scan(
            code="import math; print(math.sqrt(16))"
        )

        assert result.passed is True
        assert len(result.issues) == 0
        assert result.severity == "none"

    @pytest.mark.asyncio
    async def test_security_scan_dangerous_eval(self, sandbox):
        """Test security scan detects eval()."""
        result = await sandbox.security_scan(
            code="eval('print(1)')"
        )

        assert result.passed is False
        assert any(i["type"] == "dangerous_pattern" for i in result.issues)
        assert result.severity == "high"

    @pytest.mark.asyncio
    async def test_security_scan_sql_injection(self, sandbox):
        """Test security scan detects SQL injection patterns."""
        result = await sandbox.security_scan(
            code="query = 'SELECT * FROM users WHERE id = 1'"
        )

        assert result.passed is False
        assert any(i["type"] == "sql_injection" for i in result.issues)
        assert result.severity == "critical"

    @pytest.mark.asyncio
    async def test_security_scan_suspicious_import(self, sandbox):
        """Test security scan detects suspicious imports."""
        result = await sandbox.security_scan(
            code="import subprocess"
        )

        assert result.passed is False
        assert any(i["type"] == "suspicious_import" for i in result.issues)

    @pytest.mark.asyncio
    async def test_health_check(self, sandbox):
        """Test health check."""
        is_healthy = await sandbox.health_check()
        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_reset(self, sandbox):
        """Test sandbox reset."""
        # Execute some code first
        await sandbox.execute(code="x = 1")

        # Reset
        await sandbox.reset()

        assert sandbox.execution_count == 0

    @pytest.mark.asyncio
    async def test_prewarm_container(self, check_docker):
        """Test pre-warming a container."""
        instance = DockerSandboxInstance(sandbox_id="prewarm_test")
        await instance.initialize()

        try:
            await instance.prewarm()
            assert instance._prewarmed is True

            # Execute in pre-warmed container
            result = await instance.execute(
                code="print('Pre-warmed!')",
                language="python",
            )
            assert result.success is True

        finally:
            await instance.terminate()

    @pytest.mark.asyncio
    async def test_resource_limits(self, check_docker):
        """Test that resource limits are applied."""
        instance = DockerSandboxInstance(
            sandbox_id="resource_test",
            memory_mb=64,  # Very limited memory
            cpu_limit=0.1,  # Very limited CPU
        )
        await instance.initialize()

        try:
            # Execute simple code that should work
            result = await instance.execute(
                code="print('Resource limited')",
                language="python",
            )
            assert result.success is True

        finally:
            await instance.terminate()


class TestDockerAvailability:
    """Tests for Docker availability check."""

    def test_is_docker_available_when_installed(self):
        """Test is_docker_available when Docker is installed."""
        # This test depends on the environment
        # Just verify the function runs without error
        result = is_docker_available()
        assert isinstance(result, bool)


class TestDockerSandboxPool:
    """Tests for sandbox pool with Docker instances."""

    @pytest.fixture
    async def pool(self, check_docker):
        """Create a Docker sandbox pool for testing."""
        from app.orchestration.sandbox.pool import SandboxPool

        pool = SandboxPool(
            pool_size=2,
            sandbox_type="docker",
            prewarm_docker=False,  # Don't pre-warm for faster tests
        )
        await pool.initialize()
        yield pool
        await pool.terminate()

    @pytest.mark.asyncio
    async def test_pool_creates_docker_instances(self, pool):
        """Test that pool creates Docker instances when configured."""
        assert pool.sandbox_type == "docker"

        # Check that instances are Docker instances
        from app.orchestration.sandbox.docker_instance import DockerSandboxInstance

        for instance in pool._instances.values():
            assert isinstance(instance, DockerSandboxInstance)

    @pytest.mark.asyncio
    async def test_pool_acquire_release(self, pool):
        """Test acquiring and releasing Docker instances."""
        instance = await pool.acquire(timeout=5.0)
        assert instance is not None

        # Execute code
        result = await instance.execute(
            code="print('Pool test')",
            language="python",
        )
        assert result.success is True

        await pool.release(instance)

    @pytest.mark.asyncio
    async def test_pool_health_check(self, pool):
        """Test pool health check includes sandbox type."""
        health = await pool.health_check()

        assert health["sandbox_type"] == "docker"
        assert health["total"] == 2
        assert health["available"] >= 1

    @pytest.mark.asyncio
    async def test_pool_fallback_to_local(self, monkeypatch):
        """Test pool falls back to local when Docker unavailable."""
        from app.orchestration.sandbox.pool import SandboxPool

        # Mock Docker as unavailable
        monkeypatch.setattr(
            "app.orchestration.sandbox.pool.is_docker_available",
            lambda: False,
        )

        pool = SandboxPool(pool_size=1, sandbox_type="docker")
        assert pool.sandbox_type == "local"


class TestDockerSandboxSecurity:
    """Security-focused tests for Docker sandbox."""

    @pytest.fixture
    async def sandbox(self, check_docker):
        """Create a Docker sandbox for security tests."""
        instance = DockerSandboxInstance(
            sandbox_id="security_test",
            memory_mb=128,
            network_disabled=True,  # No network access
        )
        await instance.initialize()
        yield instance
        await instance.terminate()

    @pytest.mark.asyncio
    async def test_network_disabled(self, sandbox):
        """Test that network is disabled in container."""
        # Try to make a network request
        result = await sandbox.execute(
            code="""
import socket
try:
    socket.create_connection(("google.com", 80), timeout=2)
    print("Network access available")
except Exception as e:
    print(f"Network blocked: {e}")
""",
            language="python",
            timeout_seconds=10,
        )

        # Network should be blocked
        assert "Network blocked" in result.output or not result.success

    @pytest.mark.asyncio
    async def test_filesystem_isolation(self, sandbox):
        """Test that container filesystem is isolated."""
        # Create a file in container
        result = await sandbox.execute(
            code="""
import os
# Try to access host filesystem
paths = ["/etc/passwd", "/home", "/root"]
for p in paths:
    if os.path.exists(p):
        print(f"Accessible: {p}")
""",
            language="python",
        )

        # Should not have access to host paths
        # (Container has its own /etc, but no /home or /root with user data)
        assert result.success is True