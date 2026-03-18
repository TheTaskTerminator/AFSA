"""Sandbox pool management."""
import asyncio
import logging
import uuid
from typing import Optional

from app.config import settings
from app.orchestration.sandbox.instance import (
    LocalSandboxInstance,
    SandboxInstance,
    SandboxStatus,
)

logger = logging.getLogger(__name__)


class SandboxPool:
    """Pool manager for sandbox instances."""

    def __init__(
        self,
        pool_size: int = settings.sandbox_pool_size,
        timeout_seconds: int = settings.sandbox_timeout_seconds,
    ):
        self._pool_size = pool_size
        self._timeout = timeout_seconds
        self._instances: dict[str, SandboxInstance] = {}
        self._available: asyncio.Queue[str] = asyncio.Queue()
        self._initialized = False
        self._semaphore = asyncio.Semaphore(pool_size)

    async def initialize(self) -> None:
        """Initialize sandbox pool with pre-warmed instances."""
        if self._initialized:
            return

        logger.info(f"Initializing sandbox pool with {self._pool_size} instances...")

        # Create and initialize instances
        tasks = []
        for i in range(self._pool_size):
            sandbox_id = str(uuid.uuid4())[:8]
            instance = LocalSandboxInstance(
                sandbox_id=sandbox_id,
                timeout_seconds=self._timeout,
            )
            self._instances[sandbox_id] = instance
            tasks.append(instance.initialize())

        # Wait for all instances to initialize
        await asyncio.gather(*tasks, return_exceptions=True)

        # Add all instance IDs to available queue
        for sandbox_id in self._instances:
            await self._available.put(sandbox_id)

        self._initialized = True
        logger.info(f"Sandbox pool initialized with {len(self._instances)} instances")

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