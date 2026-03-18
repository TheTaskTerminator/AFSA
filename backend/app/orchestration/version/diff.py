"""Diff calculation for snapshots."""
import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DiffEntry:
    """A single diff entry."""

    path: str
    change_type: str  # added, modified, deleted
    old_hash: str | None = None
    new_hash: str | None = None


@dataclass
class DiffResult:
    """Result of diff calculation."""

    added: list[DiffEntry] = field(default_factory=list)
    modified: list[DiffEntry] = field(default_factory=list)
    deleted: list[DiffEntry] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """Check if there are no changes."""
        return not (self.added or self.modified or self.deleted)

    @property
    def total_changes(self) -> int:
        """Get total number of changes."""
        return len(self.added) + len(self.modified) + len(self.deleted)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "added": [{"path": e.path, "hash": e.new_hash} for e in self.added],
            "modified": [
                {"path": e.path, "old_hash": e.old_hash, "new_hash": e.new_hash}
                for e in self.modified
            ],
            "deleted": [{"path": e.path, "hash": e.old_hash} for e in self.deleted],
            "total_changes": self.total_changes,
        }


class DiffCalculator:
    """Calculate diffs between snapshots."""

    @staticmethod
    def compute_hash(content: bytes) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content).hexdigest()

    @classmethod
    def compare_trees(
        cls,
        old_tree: dict[str, str],
        new_tree: dict[str, str],
    ) -> DiffResult:
        """Compare two tree structures and return diff.

        Args:
            old_tree: Dict mapping path to content hash
            new_tree: Dict mapping path to content hash

        Returns:
            DiffResult with added, modified, and deleted entries.
        """
        result = DiffResult()

        old_paths = set(old_tree.keys())
        new_paths = set(new_tree.keys())

        # Added files
        for path in new_paths - old_paths:
            result.added.append(
                DiffEntry(
                    path=path,
                    change_type="added",
                    new_hash=new_tree[path],
                )
            )

        # Deleted files
        for path in old_paths - new_paths:
            result.deleted.append(
                DiffEntry(
                    path=path,
                    change_type="deleted",
                    old_hash=old_tree[path],
                )
            )

        # Modified files
        for path in old_paths & new_paths:
            if old_tree[path] != new_tree[path]:
                result.modified.append(
                    DiffEntry(
                        path=path,
                        change_type="modified",
                        old_hash=old_tree[path],
                        new_hash=new_tree[path],
                    )
                )

        return result

    @classmethod
    def compute_tree_hash(cls, tree: dict[str, str]) -> str:
        """Compute a hash for the entire tree structure.

        Args:
            tree: Dict mapping path to content hash

        Returns:
            Combined hash of all entries.
        """
        # Sort paths for deterministic ordering
        sorted_paths = sorted(tree.keys())

        # Combine all path:hash pairs
        combined = "".join(f"{path}:{hash}" for path, hash in [(p, tree[p]) for p in sorted_paths])

        return hashlib.sha256(combined.encode()).hexdigest()