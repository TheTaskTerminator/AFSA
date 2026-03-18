"""Sandbox module for code execution."""
from app.orchestration.sandbox.pool import SandboxPool, get_sandbox_pool
from app.orchestration.sandbox.instance import (
    SandboxInstance,
    SandboxStatus,
    ExecutionResult,
    SecurityScanResult,
    LocalSandboxInstance,
)
from app.orchestration.sandbox.runner import SandboxRunner, get_sandbox_runner, VerificationResult

# Docker support is optional
try:
    from app.orchestration.sandbox.docker_instance import (
        DockerSandboxInstance,
        is_docker_available,
    )
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    is_docker_available = lambda: False

__all__ = [
    "SandboxPool",
    "get_sandbox_pool",
    "SandboxInstance",
    "SandboxStatus",
    "ExecutionResult",
    "SecurityScanResult",
    "LocalSandboxInstance",
    "DockerSandboxInstance",
    "is_docker_available",
    "DOCKER_AVAILABLE",
    "SandboxRunner",
    "get_sandbox_runner",
    "VerificationResult",
]