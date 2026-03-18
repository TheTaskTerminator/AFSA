"""Version control module."""
from app.orchestration.version.service import VersionControlService, get_version_control
from app.orchestration.version.diff import DiffCalculator, DiffResult

__all__ = [
    "VersionControlService",
    "get_version_control",
    "DiffCalculator",
    "DiffResult",
]