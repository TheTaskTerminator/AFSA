"""Sandbox instance abstraction."""
import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SandboxStatus(str, Enum):
    """Sandbox instance status."""

    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    TERMINATED = "terminated"


@dataclass
class ExecutionResult:
    """Result of code execution."""

    success: bool
    output: str
    error: Optional[str] = None
    exit_code: int = 0
    execution_time_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SecurityScanResult:
    """Result of security scan."""

    passed: bool
    issues: list[dict[str, Any]] = field(default_factory=list)
    severity: str = "none"  # none, low, medium, high, critical


class SandboxInstance(ABC):
    """Abstract base class for sandbox instances."""

    def __init__(self, sandbox_id: str):
        self.sandbox_id = sandbox_id
        self.status = SandboxStatus.INITIALIZING
        self.created_at = datetime.utcnow()
        self.last_used_at: Optional[datetime] = None
        self.execution_count = 0
        self._lock = asyncio.Lock()

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the sandbox instance."""
        pass

    @abstractmethod
    async def terminate(self) -> None:
        """Terminate the sandbox instance."""
        pass

    @abstractmethod
    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout_seconds: int = 60,
        env_vars: Optional[dict[str, str]] = None,
    ) -> ExecutionResult:
        """Execute code in the sandbox."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if sandbox is healthy."""
        pass

    @abstractmethod
    async def reset(self) -> None:
        """Reset sandbox to clean state."""
        pass

    @abstractmethod
    async def security_scan(self, code: str) -> SecurityScanResult:
        """Run security scan on code."""
        pass

    async def acquire(self) -> None:
        """Acquire lock for exclusive access."""
        await self._lock.acquire()
        self.status = SandboxStatus.BUSY
        self.last_used_at = datetime.utcnow()

    def release(self) -> None:
        """Release lock after use."""
        self._lock.release()
        self.status = SandboxStatus.READY
        self.execution_count += 1

    def is_available(self) -> bool:
        """Check if sandbox is available for use."""
        return self.status == SandboxStatus.READY and not self._lock.locked()


class LocalSandboxInstance(SandboxInstance):
    """Local sandbox implementation using subprocess isolation.

    Note: This is a simplified implementation for development.
    Production should use Docker or Firecracker for proper isolation.
    """

    # Dangerous patterns for basic security scanning
    DANGEROUS_PATTERNS = [
        "import os",
        "import subprocess",
        "import sys",
        "__import__",
        "eval(",
        "exec(",
        "compile(",
        "open(",
        "file(",
        "input(",
        "raw_input(",
    ]

    def __init__(self, sandbox_id: str, timeout_seconds: int = 60):
        super().__init__(sandbox_id)
        self._timeout = timeout_seconds
        self._working_dir: Optional[str] = None

    async def initialize(self) -> None:
        """Initialize local sandbox."""
        import tempfile

        self._working_dir = tempfile.mkdtemp(prefix=f"sandbox_{self.sandbox_id}_")
        self.status = SandboxStatus.READY
        logger.info(f"Initialized local sandbox {self.sandbox_id}")

    async def terminate(self) -> None:
        """Terminate sandbox and cleanup."""
        import shutil

        if self._working_dir:
            try:
                shutil.rmtree(self._working_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup sandbox dir: {e}")

        self.status = SandboxStatus.TERMINATED
        logger.info(f"Terminated sandbox {self.sandbox_id}")

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout_seconds: int = 60,
        env_vars: Optional[dict[str, str]] = None,
    ) -> ExecutionResult:
        """Execute code using subprocess with timeout."""
        import subprocess
        import time

        if language != "python":
            return ExecutionResult(
                success=False,
                output="",
                error=f"Unsupported language: {language}",
            )

        start_time = time.time()

        try:
            # Run code in subprocess with restricted environment
            result = subprocess.run(
                ["python3", "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=self._working_dir,
                env={"PYTHONDONTWRITEBYTECODE": "1", **(env_vars or {})},
            )

            execution_time_ms = int((time.time() - start_time) * 1000)

            return ExecutionResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
                exit_code=result.returncode,
                execution_time_ms=execution_time_ms,
            )

        except subprocess.TimeoutExpired:
            execution_time_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                success=False,
                output="",
                error=f"Execution timed out after {timeout_seconds} seconds",
                exit_code=-1,
                execution_time_ms=execution_time_ms,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error=str(e),
                exit_code=-1,
            )

    async def health_check(self) -> bool:
        """Check if sandbox is healthy."""
        return self.status in (SandboxStatus.READY, SandboxStatus.BUSY)

    async def reset(self) -> None:
        """Reset sandbox state."""
        import shutil

        if self._working_dir:
            # Clear working directory
            for item in shutil._listdir(self._working_dir):
                item_path = f"{self._working_dir}/{item}"
                try:
                    if shutil._isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        shutil._remove(item_path)
                except Exception:
                    pass

        self.execution_count = 0
        logger.debug(f"Reset sandbox {self.sandbox_id}")

    async def security_scan(self, code: str) -> SecurityScanResult:
        """Run basic security scan on code."""
        issues = []
        severity = "none"

        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in code:
                issues.append(
                    {
                        "type": "dangerous_pattern",
                        "pattern": pattern,
                        "message": f"Potentially dangerous pattern detected: {pattern}",
                    }
                )
                severity = "medium"

        # Check for SQL injection patterns
        sql_patterns = ["SELECT *", "DROP TABLE", "-- ", "'; "]
        for pattern in sql_patterns:
            if pattern.lower() in code.lower():
                issues.append(
                    {
                        "type": "sql_injection",
                        "pattern": pattern,
                        "message": "Potential SQL injection pattern detected",
                    }
                )
                severity = "high"

        return SecurityScanResult(
            passed=len(issues) == 0,
            issues=issues,
            severity=severity,
        )