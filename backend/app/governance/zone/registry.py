"""Dynamic zone registration and path mapping.

This module provides a flexible zone management system that allows
runtime registration of zones and their associated paths.
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ZoneType(str, Enum):
    """Zone types for resource classification."""

    MUTABLE = "mutable"
    IMMUTABLE = "immutable"


@dataclass
class ZoneConfig:
    """Configuration for a single zone."""

    name: str
    zone_type: ZoneType
    paths: List[str]
    description: str = ""
    writable_by: List[str] = field(default_factory=lambda: ["admin"])
    readable_by: List[str] = field(default_factory=lambda: ["admin", "developer", "viewer"])
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Normalize paths after initialization."""
        self.paths = [self._normalize_path(p) for p in self.paths]

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normalize a path for consistent matching."""
        # Convert to forward slashes and remove trailing slash
        normalized = path.replace("\\", "/").rstrip("/")
        if not normalized.startswith("/"):
            normalized = "/" + normalized
        return normalized


@dataclass
class ZoneMatchResult:
    """Result of a zone path match operation."""

    matched: bool
    zone_name: Optional[str] = None
    zone_type: Optional[ZoneType] = None
    matched_path: Optional[str] = None


class ZoneRegistry:
    """Dynamic zone registration and path mapping.

    This registry allows runtime registration of zones with their
    associated paths and access policies.

    Example:
        registry = ZoneRegistry()
        registry.register_zone("auth", ZoneConfig(
            name="auth",
            zone_type=ZoneType.IMMUTABLE,
            paths=["app/business/immutable/auth", "/immutable/auth"],
            description="Core authentication logic",
            writable_by=["admin"],
        ))

        # Check if path is in immutable zone
        result = registry.get_zone_for_path("app/business/immutable/auth/user.py")
        assert result.zone_type == ZoneType.IMMUTABLE
    """

    def __init__(self):
        self._zones: Dict[str, ZoneConfig] = {}
        self._path_index: Dict[str, str] = {}  # normalized_path -> zone_name
        self._initialized = False

    def register_zone(self, config: ZoneConfig) -> None:
        """Register a zone with its configuration.

        Args:
            config: Zone configuration

        Raises:
            ValueError: If zone name already exists
        """
        if config.name in self._zones:
            raise ValueError(f"Zone '{config.name}' already registered")

        self._zones[config.name] = config

        # Index paths for fast lookup
        for path in config.paths:
            normalized = ZoneConfig._normalize_path(path)
            self._path_index[normalized] = config.name

        logger.info(f"Registered zone '{config.name}' with {len(config.paths)} paths")

    def unregister_zone(self, name: str) -> bool:
        """Unregister a zone.

        Args:
            name: Zone name to unregister

        Returns:
            True if zone was removed, False if not found
        """
        if name not in self._zones:
            return False

        config = self._zones[name]

        # Remove from path index
        for path in config.paths:
            normalized = ZoneConfig._normalize_path(path)
            self._path_index.pop(normalized, None)

        del self._zones[name]
        logger.info(f"Unregistered zone '{name}'")
        return True

    def get_zone(self, name: str) -> Optional[ZoneConfig]:
        """Get zone configuration by name.

        Args:
            name: Zone name

        Returns:
            Zone configuration or None if not found
        """
        return self._zones.get(name)

    def get_zone_for_path(self, path: str) -> ZoneMatchResult:
        """Determine which zone a path belongs to.

        Args:
            path: File or resource path to check

        Returns:
            ZoneMatchResult with match details
        """
        normalized = ZoneConfig._normalize_path(path)

        # Try exact match first
        if normalized in self._path_index:
            zone_name = self._path_index[normalized]
            config = self._zones[zone_name]
            return ZoneMatchResult(
                matched=True,
                zone_name=zone_name,
                zone_type=config.zone_type,
                matched_path=normalized,
            )

        # Try prefix match (longest match wins)
        best_match: Optional[str] = None
        best_match_len = 0

        for indexed_path, zone_name in self._path_index.items():
            if normalized.startswith(indexed_path):
                if len(indexed_path) > best_match_len:
                    best_match = zone_name
                    best_match_len = len(indexed_path)

        if best_match:
            config = self._zones[best_match]
            return ZoneMatchResult(
                matched=True,
                zone_name=best_match,
                zone_type=config.zone_type,
                matched_path=normalized[:best_match_len],
            )

        # No match - default to mutable
        return ZoneMatchResult(
            matched=False,
            zone_type=ZoneType.MUTABLE,
        )

    def is_immutable_path(self, path: str) -> bool:
        """Check if a path is in an immutable zone.

        Args:
            path: Path to check

        Returns:
            True if path is in an immutable zone
        """
        result = self.get_zone_for_path(path)
        return result.zone_type == ZoneType.IMMUTABLE

    def get_all_zones(self) -> Dict[str, ZoneConfig]:
        """Get all registered zones.

        Returns:
            Dictionary of zone name to configuration
        """
        return self._zones.copy()

    def get_zones_by_type(self, zone_type: ZoneType) -> List[ZoneConfig]:
        """Get all zones of a specific type.

        Args:
            zone_type: Zone type to filter by

        Returns:
            List of matching zone configurations
        """
        return [
            config for config in self._zones.values()
            if config.zone_type == zone_type
        ]

    def can_write(self, path: str, roles: Set[str]) -> bool:
        """Check if a user with given roles can write to a path.

        Args:
            path: Path to check
            roles: Set of user roles

        Returns:
            True if write is allowed
        """
        result = self.get_zone_for_path(path)

        if not result.matched:
            # Unregistered path - allow for admin and developer
            return "admin" in roles or "developer" in roles

        config = self._zones.get(result.zone_name)
        if not config:
            return False

        # Check if any of the user's roles are in writable_by
        return any(role in config.writable_by for role in roles)

    def can_read(self, path: str, roles: Set[str]) -> bool:
        """Check if a user with given roles can read a path.

        Args:
            path: Path to check
            roles: Set of user roles

        Returns:
            True if read is allowed
        """
        result = self.get_zone_for_path(path)

        if not result.matched:
            # Unregistered path - allow all authenticated users
            return True

        config = self._zones.get(result.zone_name)
        if not config:
            return True

        # Check if any of the user's roles are in readable_by
        return any(role in config.readable_by for role in roles)

    def load_from_config(self, config_dict: Dict[str, Any]) -> int:
        """Load zones from a configuration dictionary.

        Args:
            config_dict: Configuration dictionary with zone definitions

        Returns:
            Number of zones loaded

        Example config:
            {
                "immutable": {
                    "auth": {
                        "path": "app/business/immutable/auth",
                        "description": "Core authentication",
                        "writable_by": ["admin"]
                    }
                },
                "mutable": {
                    "rules": {
                        "path": "app/business/mutable/rules",
                        "description": "Business rules"
                    }
                }
            }
        """
        count = 0

        # Load immutable zones
        for name, zone_config in config_dict.get("immutable", {}).items():
            paths = zone_config.get("path", [])
            if isinstance(paths, str):
                paths = [paths]

            self.register_zone(ZoneConfig(
                name=name,
                zone_type=ZoneType.IMMUTABLE,
                paths=paths,
                description=zone_config.get("description", ""),
                writable_by=zone_config.get("writable_by", ["admin"]),
                readable_by=zone_config.get("readable_by", ["admin", "developer", "viewer"]),
            ))
            count += 1

        # Load mutable zones
        for name, zone_config in config_dict.get("mutable", {}).items():
            paths = zone_config.get("path", [])
            if isinstance(paths, str):
                paths = [paths]

            self.register_zone(ZoneConfig(
                name=name,
                zone_type=ZoneType.MUTABLE,
                paths=paths,
                description=zone_config.get("description", ""),
                writable_by=zone_config.get("writable_by", ["admin", "developer"]),
                readable_by=zone_config.get("readable_by", ["admin", "developer", "viewer"]),
            ))
            count += 1

        self._initialized = True
        logger.info(f"Loaded {count} zones from configuration")
        return count

    def clear(self) -> None:
        """Clear all registered zones."""
        self._zones.clear()
        self._path_index.clear()
        self._initialized = False
        logger.info("Cleared all zones")


# Global registry instance
_registry: Optional[ZoneRegistry] = None


def get_zone_registry() -> ZoneRegistry:
    """Get or create the global zone registry.

    Returns:
        Global ZoneRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ZoneRegistry()
    return _registry


def initialize_zones(config: Optional[Dict[str, Any]] = None) -> ZoneRegistry:
    """Initialize zones from configuration.

    Args:
        config: Optional zone configuration. If not provided,
                uses default zones.

    Returns:
        Initialized ZoneRegistry
    """
    registry = get_zone_registry()
    registry.clear()

    if config is None:
        # Use default configuration
        config = _get_default_zone_config()

    registry.load_from_config(config)
    return registry


def _get_default_zone_config() -> Dict[str, Any]:
    """Get default zone configuration.

    Returns:
        Default zone configuration dictionary
    """
    return {
        "immutable": {
            "auth": {
                "path": ["app/business/immutable/auth", "/immutable/auth"],
                "description": "Core authentication logic",
                "writable_by": ["admin"],
            },
            "core": {
                "path": ["app/business/immutable/core", "/immutable/core"],
                "description": "Core system components",
                "writable_by": ["admin"],
            },
            "security": {
                "path": ["app/business/immutable/security", "/immutable/security"],
                "description": "Security policies and enforcement",
                "writable_by": ["admin"],
            },
            "config": {
                "path": ["app/business/immutable/config", "/immutable/config"],
                "description": "System configuration",
                "writable_by": ["admin"],
            },
            "database": {
                "path": ["app/business/immutable/database", "/immutable/database"],
                "description": "Core database models and migrations",
                "writable_by": ["admin"],
            },
        },
        "mutable": {
            "rules": {
                "path": ["app/business/mutable/rules", "/mutable/rules"],
                "description": "Business rules configuration",
                "writable_by": ["admin", "developer"],
            },
            "ui_config": {
                "path": ["app/business/mutable/ui_config", "/mutable/ui_config"],
                "description": "UI configuration",
                "writable_by": ["admin", "developer"],
            },
            "extensions": {
                "path": ["app/business/mutable/extensions", "/mutable/extensions"],
                "description": "Custom extensions and plugins",
                "writable_by": ["admin", "developer"],
            },
        },
    }