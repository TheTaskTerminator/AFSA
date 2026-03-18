"""Version control service for snapshot management."""
import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.snapshot import Object, Snapshot
from app.orchestration.version.diff import DiffCalculator, DiffResult

logger = logging.getLogger(__name__)


class VersionControlService:
    """Service for managing snapshots and version control."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_snapshot(
        self,
        content: dict[str, bytes],
        message: Optional[str] = None,
        task_id: Optional[UUID] = None,
        parent_id: Optional[str] = None,
    ) -> Snapshot:
        """Create a new snapshot from content.

        Args:
            content: Dict mapping file paths to content bytes
            message: Commit message
            task_id: Associated task ID
            parent_id: Parent snapshot ID

        Returns:
            Created Snapshot instance.
        """
        # Store all objects first
        tree: dict[str, str] = {}
        for path, data in content.items():
            content_hash = await self._store_object(data)
            tree[path] = content_hash

        # Compute tree hash
        tree_hash = DiffCalculator.compute_tree_hash(tree)

        # Compute snapshot ID (commit hash)
        snapshot_data = {
            "tree_hash": tree_hash,
            "tree": tree,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "parent_id": parent_id,
        }
        snapshot_id = hashlib.sha256(
            json.dumps(snapshot_data, sort_keys=True).encode()
        ).hexdigest()

        # Create snapshot record
        snapshot = Snapshot(
            id=snapshot_id,
            task_id=task_id,
            parent_id=parent_id,
            tree_hash=tree_hash,
            message=message,
            snap_metadata={"tree": tree},
        )

        self._session.add(snapshot)
        await self._session.flush()
        await self._session.refresh(snapshot)

        logger.info(f"Created snapshot {snapshot_id}")
        return snapshot

    async def _store_object(self, content: bytes) -> str:
        """Store an object and return its hash."""
        content_hash = hashlib.sha256(content).hexdigest()

        # Check if object already exists
        result = await self._session.execute(
            select(Object).where(Object.hash == content_hash)
        )
        existing = result.scalar_one_or_none()

        if existing:
            return content_hash

        # Create new object
        obj = Object(
            hash=content_hash,
            type="blob",
            content=content,
            size=len(content),
        )
        self._session.add(obj)
        await self._session.flush()

        return content_hash

    async def get_snapshot(self, snapshot_id: str) -> Optional[Snapshot]:
        """Get a snapshot by ID."""
        result = await self._session.execute(
            select(Snapshot).where(Snapshot.id == snapshot_id)
        )
        return result.scalar_one_or_none()

    async def get_snapshot_content(
        self, snapshot_id: str
    ) -> Optional[dict[str, bytes]]:
        """Get the content of a snapshot.

        Args:
            snapshot_id: Snapshot ID

        Returns:
            Dict mapping file paths to content bytes.
        """
        snapshot = await self.get_snapshot(snapshot_id)
        if not snapshot:
            return None

        tree = snapshot.snap_metadata.get("tree", {})
        content: dict[str, bytes] = {}

        for path, content_hash in tree.items():
            result = await self._session.execute(
                select(Object).where(Object.hash == content_hash)
            )
            obj = result.scalar_one_or_none()
            if obj:
                content[path] = obj.content

        return content

    async def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Snapshot]:
        """Get snapshot history.

        Args:
            limit: Maximum number of snapshots
            offset: Offset for pagination

        Returns:
            List of Snapshot instances in reverse chronological order.
        """
        result = await self._session.execute(
            select(Snapshot)
            .order_by(Snapshot.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_history_for_task(
        self,
        task_id: UUID,
        limit: int = 50,
    ) -> list[Snapshot]:
        """Get snapshot history for a specific task.

        Args:
            task_id: Task UUID
            limit: Maximum number of snapshots

        Returns:
            List of Snapshot instances for the task.
        """
        result = await self._session.execute(
            select(Snapshot)
            .where(Snapshot.task_id == task_id)
            .order_by(Snapshot.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def compare_snapshots(
        self,
        old_snapshot_id: str,
        new_snapshot_id: str,
    ) -> Optional[DiffResult]:
        """Compare two snapshots and return the diff.

        Args:
            old_snapshot_id: Old snapshot ID
            new_snapshot_id: New snapshot ID

        Returns:
            DiffResult or None if either snapshot not found.
        """
        old_snapshot = await self.get_snapshot(old_snapshot_id)
        new_snapshot = await self.get_snapshot(new_snapshot_id)

        if not old_snapshot or not new_snapshot:
            return None

        old_tree = old_snapshot.snap_metadata.get("tree", {})
        new_tree = new_snapshot.snap_metadata.get("tree", {})

        return DiffCalculator.compare_trees(old_tree, new_tree)

    async def restore_snapshot(
        self,
        snapshot_id: str,
    ) -> Optional[dict[str, bytes]]:
        """Restore content from a snapshot.

        Args:
            snapshot_id: Snapshot ID to restore

        Returns:
            Dict mapping file paths to content bytes.
        """
        return await self.get_snapshot_content(snapshot_id)

    async def get_object(self, content_hash: str) -> Optional[Object]:
        """Get an object by its hash."""
        result = await self._session.execute(
            select(Object).where(Object.hash == content_hash)
        )
        return result.scalar_one_or_none()

    async def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot.

        Note: Objects are not deleted as they may be referenced by other snapshots.

        Args:
            snapshot_id: Snapshot ID

        Returns:
            True if deleted, False if not found.
        """
        snapshot = await self.get_snapshot(snapshot_id)
        if not snapshot:
            return False

        await self._session.delete(snapshot)
        await self._session.flush()

        logger.info(f"Deleted snapshot {snapshot_id}")
        return True

    async def get_children(self, snapshot_id: str) -> list[Snapshot]:
        """Get all children of a snapshot.

        Args:
            snapshot_id: Parent snapshot ID

        Returns:
            List of child Snapshot instances.
        """
        result = await self._session.execute(
            select(Snapshot).where(Snapshot.parent_id == snapshot_id)
        )
        return list(result.scalars().all())


# Global version control service factory
def get_version_control(session: AsyncSession) -> VersionControlService:
    """Get version control service instance."""
    return VersionControlService(session)