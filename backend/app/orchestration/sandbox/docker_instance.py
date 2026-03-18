"""Docker-based sandbox implementation for secure code execution.

This module provides true isolation using Docker containers with:
- Resource limits (CPU, memory)
- Network isolation
- Filesystem isolation
- Execution timeout
- Pre-warm container pool for performance
"""
import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from app.config import settings
from app.orchestration.sandbox.instance import (
    ExecutionResult,
    SandboxInstance,
    SandboxStatus,
    SecurityScanResult,
)

logger = logging.getLogger(__name__)

# Docker SDK is optional - check availability
try:
    import docker
    from docker.errors import DockerException, ImageNotFound, APIError
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    docker = None
    DockerException = Exception
    ImageNotFound = Exception
    APIError = Exception


class DockerSandboxInstance(SandboxInstance):
    """Docker-based sandbox instance for secure code execution.

    Features:
    - True container isolation
    - CPU and memory limits
    - Network isolation (configurable)
    - Automatic container cleanup
    - Pre-warm pool support
    """

    # Safe modules whitelist for security scan
    SAFE_MODULES = {
        "math", "random", "statistics", "itertools", "collections",
        "functools", "operator", "datetime", "time", "re", "json",
        "typing", "dataclasses", "enum", "abc", "copy", "decimal",
        "fractions", "numbers", "string", "textwrap", "unicodedata",
    }

    # Dangerous patterns for security scanning
    DANGEROUS_PATTERNS = [
        "__import__",
        "eval(",
        "exec(",
        "compile(",
        "getattr(",
        "setattr(",
        "delattr(",
        "globals()",
        "locals()",
        "vars()",
        "dir()",
        "breakpoint(",
    ]

    def __init__(
        self,
        sandbox_id: str,
        image: str = None,
        memory_mb: int = None,
        cpu_limit: float = None,
        network_disabled: bool = None,
        timeout_seconds: int = None,
    ):
        """Initialize Docker sandbox instance.

        Args:
            sandbox_id: Unique identifier for this sandbox
            image: Docker image to use
            memory_mb: Memory limit in megabytes
            cpu_limit: CPU limit (1.0 = 1 CPU core)
            network_disabled: Whether to disable network
            timeout_seconds: Execution timeout
        """
        super().__init__(sandbox_id)

        if not DOCKER_AVAILABLE:
            raise RuntimeError(
                "Docker SDK not available. Install with: pip install docker"
            )

        self._image = image or settings.docker_sandbox_image
        self._memory_mb = memory_mb or settings.docker_sandbox_memory_mb
        self._cpu_limit = cpu_limit or settings.docker_sandbox_cpu_limit
        self._network_disabled = (
            network_disabled
            if network_disabled is not None
            else settings.docker_sandbox_network_disabled
        )
        self._timeout = timeout_seconds or settings.docker_sandbox_timeout_seconds

        self._client: Optional[docker.DockerClient] = None
        self._container: Optional[docker.models.containers.Container] = None
        self._prewarmed = False

    async def initialize(self) -> None:
        """Initialize Docker client and optionally pre-warm container."""
        try:
            # Initialize Docker client
            self._client = docker.from_env()

            # Verify image exists
            try:
                self._client.images.get(self._image)
                logger.debug(f"Image {self._image} found locally")
            except ImageNotFound:
                logger.info(f"Pulling image {self._image}...")
                await asyncio.to_thread(
                    self._client.images.pull,
                    self._image
                )
                logger.info(f"Image {self._image} pulled successfully")

            self.status = SandboxStatus.READY
            logger.info(f"Initialized Docker sandbox {self.sandbox_id}")

        except DockerException as e:
            self.status = SandboxStatus.ERROR
            logger.error(f"Failed to initialize Docker sandbox: {e}")
            raise RuntimeError(f"Docker initialization failed: {e}")

    async def prewarm(self) -> None:
        """Pre-warm a container for faster execution.

        Creates a container in advance to reduce first execution latency.
        """
        if self._container is not None:
            return

        try:
            # Create container without starting
            self._container = await asyncio.to_thread(
                self._client.containers.create,
                image=self._image,
                command="tail -f /dev/null",  # Keep container running
                name=f"afsa_sandbox_{self.sandbox_id}",
                mem_limit=f"{self._memory_mb}m",
                cpu_quota=int(self._cpu_limit * 100000),
                network_disabled=self._network_disabled,
                auto_remove=False,
                detach=True,
                stdin_open=True,
                tty=True,
            )

            # Start container
            await asyncio.to_thread(self._container.start)
            self._prewarmed = True
            logger.debug(f"Pre-warmed container {self.sandbox_id}")

        except Exception as e:
            logger.warning(f"Failed to pre-warm container: {e}")
            self._prewarmed = False

    async def terminate(self) -> None:
        """Terminate container and cleanup resources."""
        if self._container:
            try:
                await asyncio.to_thread(self._container.stop)
                await asyncio.to_thread(self._container.remove)
            except Exception as e:
                logger.warning(f"Error cleaning up container: {e}")

        if self._client:
            try:
                self._client.close()
            except Exception:
                pass

        self._container = None
        self._client = None
        self.status = SandboxStatus.TERMINATED
        logger.info(f"Terminated Docker sandbox {self.sandbox_id}")

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout_seconds: int = 60,
        env_vars: Optional[dict[str, str]] = None,
    ) -> ExecutionResult:
        """Execute code in Docker container.

        Args:
            code: Code to execute
            language: Programming language (only python supported)
            timeout_seconds: Execution timeout
            env_vars: Environment variables

        Returns:
            ExecutionResult with output or error
        """
        if language != "python":
            return ExecutionResult(
                success=False,
                output="",
                error=f"Unsupported language: {language}",
            )

        if not self._client:
            return ExecutionResult(
                success=False,
                output="",
                error="Docker client not initialized",
            )

        import time
        start_time = time.time()
        timeout = timeout_seconds or self._timeout

        try:
            # Use pre-warmed container or create new one
            container = self._container
            temp_container = False

            if container is None or not self._prewarmed:
                # Create temporary container for this execution
                container = await asyncio.to_thread(
                    self._client.containers.run,
                    image=self._image,
                    command=["python3", "-c", code],
                    mem_limit=f"{self._memory_mb}m",
                    cpu_quota=int(self._cpu_limit * 100000),
                    network_disabled=self._network_disabled,
                    environment=env_vars,
                    remove=False,
                    detach=True,
                    stdout=True,
                    stderr=True,
                )
                temp_container = True

            else:
                # Execute in pre-warmed container
                exec_result = await asyncio.to_thread(
                    container.exec_run,
                    cmd=["python3", "-c", code],
                    environment=env_vars,
                    demux=True,
                )

                execution_time_ms = int((time.time() - start_time) * 1000)

                exit_code, (stdout, stderr) = exec_result
                output = stdout.decode("utf-8") if stdout else ""
                error = stderr.decode("utf-8") if stderr else None

                return ExecutionResult(
                    success=exit_code == 0,
                    output=output,
                    error=error,
                    exit_code=exit_code,
                    execution_time_ms=execution_time_ms,
                )

            # Wait for container to finish with timeout
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(container.wait),
                    timeout=timeout,
                )

                # Get logs
                logs = await asyncio.to_thread(
                    container.logs,
                    stdout=True,
                    stderr=True,
                )

                execution_time_ms = int((time.time() - start_time) * 1000)
                exit_code = result.get("StatusCode", -1)

                # Parse stdout/stderr
                output = logs.decode("utf-8")

                return ExecutionResult(
                    success=exit_code == 0,
                    output=output if exit_code == 0 else "",
                    error=output if exit_code != 0 else None,
                    exit_code=exit_code,
                    execution_time_ms=execution_time_ms,
                )

            except asyncio.TimeoutError:
                execution_time_ms = int((time.time() - start_time) * 1000)
                return ExecutionResult(
                    success=False,
                    output="",
                    error=f"Execution timed out after {timeout} seconds",
                    exit_code=-1,
                    execution_time_ms=execution_time_ms,
                )

            finally:
                # Cleanup temporary container
                if temp_container:
                    try:
                        await asyncio.to_thread(container.remove, force=True)
                    except Exception:
                        pass

        except APIError as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                success=False,
                output="",
                error=f"Docker API error: {e.explanation}",
                exit_code=-1,
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                exit_code=-1,
                execution_time_ms=execution_time_ms,
            )

    async def health_check(self) -> bool:
        """Check if Docker and container are healthy."""
        if not self._client:
            return False

        try:
            # Check Docker daemon
            await asyncio.to_thread(self._client.ping)

            # Check pre-warmed container if exists
            if self._container and self._prewarmed:
                self._container.reload()
                return self._container.status == "running"

            return True

        except Exception:
            return False

    async def reset(self) -> None:
        """Reset sandbox to clean state."""
        if self._container and self._prewarmed:
            # Restart pre-warmed container
            try:
                await asyncio.to_thread(self._container.restart)
                logger.debug(f"Reset pre-warmed container {self.sandbox_id}")
            except Exception as e:
                logger.warning(f"Failed to reset container: {e}")
                # Try to recreate
                self._prewarmed = False
                await self.prewarm()

        self.execution_count = 0

    async def security_scan(self, code: str) -> SecurityScanResult:
        """Run enhanced security scan on code.

        Checks for:
        - Dangerous function calls
        - Suspicious imports
        - SQL injection patterns
        - Shell command patterns
        """
        import ast
        import re

        issues = []
        severity = "none"

        # Check dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in code:
                issues.append({
                    "type": "dangerous_pattern",
                    "pattern": pattern,
                    "message": f"危险函数调用检测: {pattern}",
                    "severity": "high",
                })
                severity = "high"

        # Parse AST for deeper analysis
        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                # Check imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name.split(".")[0]
                        if module not in self.SAFE_MODULES:
                            issues.append({
                                "type": "suspicious_import",
                                "module": alias.name,
                                "message": f"可疑模块导入: {alias.name}",
                                "severity": "medium",
                            })
                            if severity == "none":
                                severity = "medium"

                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module = node.module.split(".")[0]
                        if module not in self.SAFE_MODULES:
                            issues.append({
                                "type": "suspicious_import",
                                "module": node.module,
                                "message": f"可疑模块导入: {node.module}",
                                "severity": "medium",
                            })
                            if severity == "none":
                                severity = "medium"

        except SyntaxError:
            # Code has syntax errors, let execution handle it
            pass

        # Check SQL injection patterns
        sql_patterns = [
            r"SELECT\s+.*\s+FROM",
            r"DROP\s+TABLE",
            r"DELETE\s+FROM",
            r"INSERT\s+INTO",
            r"UPDATE\s+.*\s+SET",
            r";\s*--",
            r"'\s*OR\s+'",
            r"UNION\s+SELECT",
        ]

        for pattern in sql_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append({
                    "type": "sql_injection",
                    "pattern": pattern,
                    "message": "潜在 SQL 注入模式检测",
                    "severity": "critical",
                })
                severity = "critical"

        # Check shell command patterns
        shell_patterns = [
            r"subprocess\.",
            r"os\.system",
            r"os\.popen",
            r"commands\.",
            r"popen",
        ]

        for pattern in shell_patterns:
            if re.search(pattern, code):
                issues.append({
                    "type": "shell_command",
                    "pattern": pattern,
                    "message": "Shell 命令执行检测",
                    "severity": "high",
                })
                if severity not in ("critical", "high"):
                    severity = "high"

        return SecurityScanResult(
            passed=len(issues) == 0,
            issues=issues,
            severity=severity,
        )


def is_docker_available() -> bool:
    """Check if Docker is available and running."""
    if not DOCKER_AVAILABLE:
        return False

    try:
        client = docker.from_env()
        client.ping()
        client.close()
        return True
    except Exception:
        return False