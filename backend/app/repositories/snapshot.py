"""Snapshot repository."""
import hashlib
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.snapshot import Object, Snapshot
from app.repositories.base import BaseRepository


class SnapshotRepository:
    """Snapshot repository for version control operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # Snapshot operations
    async def get(self, snapshot_id: str) -> Optional[Snapshot]:
        """Get a snapshot by ID (hash)."""
        result = await self.session.execute(
            select(Snapshot).where(Snapshot.id == snapshot_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        tree_hash: str,
        task_id: Optional[UUID] = None,
        parent_id: Optional[str] = None,
        message: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Snapshot:
        """Create a new snapshot."""
        # Generate SHA-256 hash as ID
        hash_content = f"{tree_hash}:{parent_id}:{message}"
        snapshot_id = hashlib.sha256(hash_content.encode()).hexdigest()

        snapshot = Snapshot(
            id=snapshot_id,
            task_id=task_id,
            parent_id=parent_id,
            tree_hash=tree_hash,
            message=message,
            metadata=metadata,
        )
        self.session.add(snapshot)
        await self.session.flush()
        await self.session.refresh(snapshot)
        return snapshot

    async def get_by_task(self, task_id: UUID) -> List[Snapshot]:
        """Get snapshots by task."""
        result = await self.session.execute(
            select(Snapshot)
            .where(Snapshot.task_id == task_id)
            .order_by(Snapshot.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_latest(self, limit: int = 20) -> List[Snapshot]:
        """Get latest snapshots."""
        result = await self.session.execute(
            select(Snapshot).order_by(Snapshot.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def get_children(self, parent_id: str) -> List[Snapshot]:
        """Get children of a snapshot."""
        result = await self.session.execute(
            select(Snapshot)
            .where(Snapshot.parent_id == parent_id)
            .order_by(Snapshot.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_history(self, snapshot_id: str, limit: int = 50) -> List[Snapshot]:
        """Get commit history from a snapshot."""
        history = []
        current = await self.get(snapshot_id)
        while current is not None and len(history) < limit:
            history.append(current)
            if current.parent_id is None:
                break
            current = await self.get(current.parent_id)
        return history

    # Object operations
    async def get_object(self, object_hash: str) -> Optional[Object]:
        """Get an object by hash."""
        result = await self.session.execute(
            select(Object).where(Object.hash == object_hash)
        )
        return result.scalar_one_or_none()

    async def store_object(
        self, content: bytes, object_type: str = "blob"
    ) -> Object:
        """Store an object and return its hash."""
        # Calculate SHA-256 hash
        object_hash = hashlib.sha256(content).hexdigest()

        # Check if object already exists
        existing = await self.get_object(object_hash)
        if existing is not None:
            return existing

        # Create new object
        obj = Object(
            hash=object_hash,
            type=object_type,
            content=content,
            size=len(content),
        )
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def object_exists(self, object_hash: str) -> bool:
        """Check if object exists."""
        result = await self.session.execute(
            select(Object.hash).where(Object.hash == object_hash)
        )
        return result.scalar_one_or_none() is not None

    async def get_objects_by_hashes(
        self, hashes: List[str]
    ) -> List[Object]:
        """Get multiple objects by hashes."""
        if not hashes:
            return []
        result = await self.session.execute(
            select(Object).where(Object.hash.in_(hashes))
        )
        return list(result.scalars().all())

    async def delete_object(self, object_hash: str) -> bool:
        """Delete an object by hash."""
        obj = await self.get_object(object_hash)
        if obj is None:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True