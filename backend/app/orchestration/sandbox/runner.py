"""Sandbox runner for code execution and verification."""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from app.orchestration.sandbox.instance import (
    ExecutionResult,
    SandboxInstance,
    SecurityScanResult,
)
from app.orchestration.sandbox.pool import SandboxPool, get_sandbox_pool

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of code verification."""

    passed: bool
    execution_result: Optional[ExecutionResult] = None
    security_result: Optional[SecurityScanResult] = None
    tests_passed: int = 0
    tests_total: int = 0
    errors: list[str] = field(default_factory=list)


class SandboxRunner:
    """Runner for executing and verifying code in sandbox.

    Features:
    - Code execution with isolation
    - Security scanning (SAST)
    - Test verification
    - Result collection
    """

    def __init__(self, pool: Optional[SandboxPool] = None):
        self._pool = pool
        self._verification_tasks: dict[str, asyncio.Task] = {}

    async def _ensure_pool(self) -> SandboxPool:
        """Ensure pool is initialized."""
        if self._pool is None:
            self._pool = await get_sandbox_pool()
        return self._pool

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout_seconds: int = 60,
        env_vars: Optional[dict[str, str]] = None,
        skip_security_scan: bool = False,
    ) -> ExecutionResult:
        """Execute code in sandbox.

        Args:
            code: Code to execute
            language: Programming language
            timeout_seconds: Execution timeout
            env_vars: Environment variables
            skip_security_scan: Skip security scan

        Returns:
            ExecutionResult with output or error.
        """
        pool = await self._ensure_pool()

        # Get sandbox instance
        instance = await pool.acquire(timeout=30.0)
        if instance is None:
            return ExecutionResult(
                success=False,
                output="",
                error="No available sandbox instance",
            )

        try:
            # Run security scan if not skipped
            if not skip_security_scan:
                scan_result = await instance.security_scan(code)
                if not scan_result.passed:
                    return ExecutionResult(
                        success=False,
                        output="",
                        error=f"Security scan failed: {scan_result.issues}",
                    )

            # Execute code
            result = await instance.execute(
                code=code,
                language=language,
                timeout_seconds=timeout_seconds,
                env_vars=env_vars,
            )

            return result

        finally:
            await pool.release(instance)

    async def verify(
        self,
        code: str,
        tests: Optional[str] = None,
        language: str = "python",
        timeout_seconds: int = 60,
    ) -> VerificationResult:
        """Execute code and run verification tests.

        Args:
            code: Code to verify
            tests: Test code to run
            language: Programming language
            timeout_seconds: Execution timeout

        Returns:
            VerificationResult with test results.
        """
        pool = await self._ensure_pool()

        # Get sandbox instance
        instance = await pool.acquire(timeout=30.0)
        if instance is None:
            return VerificationResult(
                passed=False,
                errors=["No available sandbox instance"],
            )

        try:
            # Run security scan
            security_result = await instance.security_scan(code)
            if not security_result.passed:
                return VerificationResult(
                    passed=False,
                    security_result=security_result,
                    errors=[f"Security issue: {i['message']}" for i in security_result.issues],
                )

            # Execute main code
            execution_result = await instance.execute(
                code=code,
                language=language,
                timeout_seconds=timeout_seconds,
            )

            if not execution_result.success:
                return VerificationResult(
                    passed=False,
                    execution_result=execution_result,
                    errors=[execution_result.error or "Execution failed"],
                )

            # Run tests if provided
            tests_passed = 0
            tests_total = 0
            test_errors: list[str] = []

            if tests:
                # Combine code and tests
                combined_code = f"{code}\n\n{tests}"
                test_result = await instance.execute(
                    code=combined_code,
                    language=language,
                    timeout_seconds=timeout_seconds,
                )

                # Parse test results from output
                if test_result.success:
                    output = test_result.output.lower()
                    # Simple test result parsing
                    if "passed" in output or "ok" in output:
                        tests_passed = 1
                        tests_total = 1
                    elif "failed" in output or "error" in output:
                        tests_total = 1
                        test_errors.append(test_result.output)
                    else:
                        tests_passed = 1
                        tests_total = 1
                else:
                    tests_total = 1
                    test_errors.append(test_result.error or "Tests failed")

            passed = (
                security_result.passed
                and execution_result.success
                and (tests_passed == tests_total if tests else True)
            )

            return VerificationResult(
                passed=passed,
                execution_result=execution_result,
                security_result=security_result,
                tests_passed=tests_passed,
                tests_total=tests_total,
                errors=test_errors,
            )

        finally:
            await pool.release(instance)

    async def execute_with_callback(
        self,
        code: str,
        callback: Any,
        language: str = "python",
        timeout_seconds: int = 60,
        task_id: Optional[UUID] = None,
    ) -> ExecutionResult:
        """Execute code and call callback with result.

        Args:
            code: Code to execute
            callback: Async callback function
            language: Programming language
            timeout_seconds: Execution timeout
            task_id: Optional task ID for tracking

        Returns:
            ExecutionResult
        """
        result = await self.execute(
            code=code,
            language=language,
            timeout_seconds=timeout_seconds,
        )

        # Call callback if provided
        if callback:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(result)
                else:
                    callback(result)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        return result

    async def batch_execute(
        self,
        code_list: list[tuple[str, str]],  # (code, language) pairs
        timeout_seconds: int = 60,
        max_concurrent: int = 3,
    ) -> list[ExecutionResult]:
        """Execute multiple code snippets concurrently.

        Args:
            code_list: List of (code, language) tuples
            timeout_seconds: Execution timeout per snippet
            max_concurrent: Maximum concurrent executions

        Returns:
            List of ExecutionResult in same order.
        """
        pool = await self._ensure_pool()
        semaphore = asyncio.Semaphore(max_concurrent)
        results: list[ExecutionResult] = []

        async def execute_one(code: str, language: str, index: int) -> None:
            async with semaphore:
                instance = await pool.acquire(timeout=30.0)
                if instance is None:
                    results.insert(index, ExecutionResult(
                        success=False,
                        output="",
                        error="No available sandbox",
                    ))
                    return

                try:
                    result = await instance.execute(
                        code=code,
                        language=language,
                        timeout_seconds=timeout_seconds,
                    )
                    results.insert(index, result)
                finally:
                    await pool.release(instance)

        # Execute all concurrently
        tasks = [
            execute_one(code, lang, i)
            for i, (code, lang) in enumerate(code_list)
        ]
        await asyncio.gather(*tasks)

        return results

    async def health_check(self) -> dict[str, Any]:
        """Check health of sandbox runner and pool."""
        pool = await self._ensure_pool()
        pool_health = await pool.health_check()

        return {
            "status": "healthy" if pool_health["available"] > 0 else "degraded",
            "pool": pool_health,
            "running_verifications": len(self._verification_tasks),
        }


# Global runner instance
_runner: Optional[SandboxRunner] = None


async def get_sandbox_runner() -> SandboxRunner:
    """Get or create sandbox runner."""
    global _runner
    if _runner is None:
        _runner = SandboxRunner()
    return _runner