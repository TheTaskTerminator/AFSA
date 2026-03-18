"""Sandbox pool management."""
import asyncio
import logging
import uuid
from typing import Literal, Optional

from app.config import settings
from app.orchestration.sandbox.instance import (
    LocalSandboxInstance,
    SandboxInstance,
    SandboxStatus,
)

logger = logging.getLogger(__name__)

# Import Docker instance if available
try:
    from app.orchestration.sandbox.docker_instance import (
        DockerSandboxInstance,
        is_docker_available,
    )
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    is_docker_available = lambda: False


class SandboxPool:
    """Pool manager for sandbox instances.

    Supports both local (subprocess) and Docker-based sandbox instances.
    Docker provides true isolation with resource limits and network control.
    """

    def __init__(
        self,
        pool_size: int = settings.sandbox_pool_size,
        timeout_seconds: int = settings.sandbox_timeout_seconds,
        sandbox_type: Literal["local", "docker"] = None,
        prewarm_docker: bool = True,
    ):
        self._pool_size = pool_size
        self._timeout = timeout_seconds
        self._sandbox_type = sandbox_type or settings.sandbox_type
        self._prewarm_docker = prewarm_docker
        self._instances: dict[str, SandboxInstance] = {}
        self._available: asyncio.Queue[str] = asyncio.Queue()
        self._initialized = False
        self._semaphore = asyncio.Semaphore(pool_size)

    @property
    def sandbox_type(self) -> str:
        """Get the sandbox type being used."""
        # Fallback to local if Docker requested but unavailable
        if self._sandbox_type == "docker" and not DOCKER_AVAILABLE:
            logger.warning("Docker requested but not available, falling back to local")
            return "local"
        if self._sandbox_type == "docker" and not is_docker_available():
            logger.warning("Docker daemon not running, falling back to local")
            return "local"
        return self._sandbox_type

    def _create_instance(self, sandbox_id: str) -> SandboxInstance:
        """Create a sandbox instance based on configured type.

        Args:
            sandbox_id: Unique identifier for the instance

        Returns:
            SandboxInstance (Local or Docker-based)
        """
        if self.sandbox_type == "docker":
            return DockerSandboxInstance(
                sandbox_id=sandbox_id,
                timeout_seconds=self._timeout,
            )
        else:
            return LocalSandboxInstance(
                sandbox_id=sandbox_id,
                timeout_seconds=self._timeout,
            )

    async def initialize(self) -> None:
        """Initialize sandbox pool with pre-warmed instances.

        For Docker sandboxes, optionally pre-warm containers for faster execution.
        """
        if self._initialized:
            return

        logger.info(
            f"Initializing {self.sandbox_type} sandbox pool "
            f"with {self._pool_size} instances..."
        )

        # Create and initialize instances
        tasks = []
        instances_to_prewarm = []

        for i in range(self._pool_size):
            sandbox_id = str(uuid.uuid4())[:8]
            instance = self._create_instance(sandbox_id)
            self._instances[sandbox_id] = instance
            tasks.append(instance.initialize())

            # Track Docker instances for pre-warming
            if self.sandbox_type == "docker" and self._prewarm_docker:
                instances_to_prewarm.append(instance)

        # Wait for all instances to initialize
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any initialization failures
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to initialize sandbox: {result}")

        # Pre-warm Docker containers
        prewarm_count = min(
            len(instances_to_prewarm),
            settings.docker_sandbox_prewarm_pool,
        )
        if prewarm_count > 0:
            logger.info(f"Pre-warming {prewarm_count} Docker containers...")
            prewarm_tasks = [
                inst.prewarm()
                for inst in instances_to_prewarm[:prewarm_count]
            ]
            await asyncio.gather(*prewarm_tasks, return_exceptions=True)

        # Add all instance IDs to available queue
        for sandbox_id in self._instances:
            await self._available.put(sandbox_id)

        self._initialized = True
        logger.info(
            f"Sandbox pool initialized with {len(self._instances)} "
            f"{self.sandbox_type} instances"
        )

    async def acquire(self, timeout: float = 30.0) -> Optional[SandboxInstance]:
        """Acquire a sandbox instance from the pool.

        Args:
            timeout: Maximum time to wait for an available instance.

        Returns:
            SandboxInstance or None if timeout.
        """
        if not self._initialized:
            await self.initialize()

        try:
            # Wait for available instance with timeout
            sandbox_id = await asyncio.wait_for(
                self._available.get(),
                timeout=timeout,
            )

            instance = self._instances.get(sandbox_id)
            if instance:
                await instance.acquire()
                logger.debug(f"Acquired sandbox {sandbox_id}")
                return instance

        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for available sandbox")
            return None
        except Exception as e:
            logger.error(f"Failed to acquire sandbox: {e}")
            return None

        return None

    async def release(self, instance: SandboxInstance) -> None:
        """Release a sandbox instance back to the pool."""
        if instance.sandbox_id not in self._instances:
            logger.warning(f"Unknown sandbox instance: {instance.sandbox_id}")
            return

        # Reset instance state
        try:
            await instance.reset()
        except Exception as e:
            logger.warning(f"Failed to reset sandbox {instance.sandbox_id}: {e}")

        instance.release()
        await self._available.put(instance.sandbox_id)
        logger.debug(f"Released sandbox {instance.sandbox_id}")

    async def terminate(self) -> None:
        """Terminate all sandbox instances."""
        logger.info("Terminating sandbox pool...")

        tasks = []
        for instance in self._instances.values():
            tasks.append(instance.terminate())

        await asyncio.gather(*tasks, return_exceptions=True)

        self._instances.clear()
        # Clear the queue
        while not self._available.empty():
            try:
                self._available.get_nowait()
            except asyncio.QueueEmpty:
                break

        self._initialized = False
        logger.info("Sandbox pool terminated")

    async def health_check(self) -> dict:
        """Check health of all sandbox instances."""
        results = {
            "sandbox_type": self.sandbox_type,
            "total": len(self._instances),
            "available": self._available.qsize(),
            "instances": {},
        }

        for sandbox_id, instance in self._instances.items():
            is_healthy = await instance.health_check()
            results["instances"][sandbox_id] = {
                "status": instance.status.value,
                "healthy": is_healthy,
                "execution_count": instance.execution_count,
            }

        return results

    async def get_instance(self, sandbox_id: str) -> Optional[SandboxInstance]:
        """Get a specific sandbox instance by ID."""
        return self._instances.get(sandbox_id)

    @property
    def pool_size(self) -> int:
        """Get configured pool size."""
        return self._pool_size

    @property
    def available_count(self) -> int:
        """Get number of available instances."""
        return self._available.qsize()


# Global sandbox pool instance
_sandbox_pool: Optional[SandboxPool] = None


async def get_sandbox_pool() -> SandboxPool:
    """Get or create sandbox pool."""
    global _sandbox_pool
    if _sandbox_pool is None:
        _sandbox_pool = SandboxPool()
        await _sandbox_pool.initialize()
    return _sandbox_pool


async def close_sandbox_pool() -> None:
    """Close sandbox pool."""
    global _sandbox_pool
    if _sandbox_pool is not None:
        await _sandbox_pool.terminate()
        _sandbox_pool = None