"""Business layer module.

This module provides the BusinessModule class for defining and organizing
business modules with their models, APIs, and dependencies.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.business.dsl import APIInterface, BusinessModel
from app.governance.zone import ZoneType


@dataclass
class BusinessModule:
    """Framework-agnostic business module definition.

    A BusinessModule represents a cohesive unit of business functionality
    that can be registered, discovered, and managed independently.

    Attributes:
        id: Unique identifier for the module (e.g., "user-management")
        name: Human-readable name (e.g., "User Management")
        version: Module version (semver format recommended)
        description: Brief description of the module's purpose
        zone: Zone type for the module (mutable or immutable)
        models: List of business models defined by this module
        apis: List of API interfaces provided by this module
        dependencies: List of module IDs this module depends on
        author: Module author or team
        tags: Tags for categorization and search
        metadata: Additional metadata
        enabled: Whether the module is currently enabled
    """

    id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    zone: ZoneType = ZoneType.MUTABLE
    models: List[BusinessModel] = field(default_factory=list)
    apis: List[APIInterface] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    author: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def add_model(self, model: BusinessModel) -> "BusinessModule":
        """Add a business model to this module.

        Args:
            model: Business model to add

        Returns:
            Self for chaining
        """
        self.models.append(model)
        return self

    def add_api(self, api: APIInterface) -> "BusinessModule":
        """Add an API interface to this module.

        Args:
            api: API interface to add

        Returns:
            Self for chaining
        """
        self.apis.append(api)
        return self

    def add_dependency(self, module_id: str) -> "BusinessModule":
        """Add a dependency on another module.

        Args:
            module_id: ID of the module this one depends on

        Returns:
            Self for chaining
        """
        if module_id not in self.dependencies:
            self.dependencies.append(module_id)
        return self

    def get_model(self, name: str) -> Optional[BusinessModel]:
        """Get a model by name.

        Args:
            name: Model name

        Returns:
            BusinessModel if found, None otherwise
        """
        for model in self.models:
            if model.name == name:
                return model
        return None

    def get_api(self, name: str) -> Optional[APIInterface]:
        """Get an API interface by name.

        Args:
            name: API name

        Returns:
            APIInterface if found, None otherwise
        """
        for api in self.apis:
            if api.name == name:
                return api
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert module to dictionary representation.

        Returns:
            Dictionary representation of the module
        """
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "zone": self.zone.value,
            "models": [{"name": m.name, "table": m.table_name} for m in self.models],
            "apis": [{"name": a.name, "base_path": a.base_path} for a in self.apis],
            "dependencies": self.dependencies,
            "author": self.author,
            "tags": self.tags,
            "enabled": self.enabled,
            "metadata": self.metadata,
        }


@dataclass
class ModuleVersion:
    """Represents a module version for dependency resolution.

    Supports semver-style version comparison.
    """

    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None

    @classmethod
    def parse(cls, version_str: str) -> "ModuleVersion":
        """Parse a version string.

        Args:
            version_str: Version string (e.g., "1.2.3" or "1.2.3-alpha")

        Returns:
            ModuleVersion instance
        """
        # Handle prerelease
        prerelease = None
        if "-" in version_str:
            version_str, prerelease = version_str.split("-", 1)

        parts = version_str.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0

        return cls(major=major, minor=minor, patch=patch, prerelease=prerelease)

    def __str__(self) -> str:
        """Return string representation."""
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            base += f"-{self.prerelease}"
        return base

    def __lt__(self, other: "ModuleVersion") -> bool:
        """Compare versions."""
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        if self.patch != other.patch:
            return self.patch < other.patch
        # Prerelease versions are less than release versions
        if self.prerelease and not other.prerelease:
            return True
        if not self.prerelease and other.prerelease:
            return False
        if self.prerelease and other.prerelease:
            return self.prerelease < other.prerelease
        return False

    def __le__(self, other: "ModuleVersion") -> bool:
        """Compare versions."""
        return self == other or self < other

    def __gt__(self, other: "ModuleVersion") -> bool:
        """Compare versions."""
        return not self <= other

    def __ge__(self, other: "ModuleVersion") -> bool:
        """Compare versions."""
        return not self < other

    def __eq__(self, other: object) -> bool:
        """Compare versions."""
        if not isinstance(other, ModuleVersion):
            return False
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
            and self.prerelease == other.prerelease
        )


@dataclass
class ModuleDependency:
    """Represents a dependency specification.

    Supports version constraints like ">=1.0.0,<2.0.0".
    """

    module_id: str
    version_constraint: Optional[str] = None

    def is_satisfied_by(self, version: ModuleVersion) -> bool:
        """Check if a version satisfies this dependency.

        Args:
            version: Version to check

        Returns:
            True if the version satisfies the constraint
        """
        if not self.version_constraint:
            return True

        constraints = self.version_constraint.split(",")
        for constraint in constraints:
            constraint = constraint.strip()
            if not self._check_constraint(version, constraint):
                return False
        return True

    def _check_constraint(self, version: ModuleVersion, constraint: str) -> bool:
        """Check a single constraint."""
        if constraint.startswith(">="):
            return version >= ModuleVersion.parse(constraint[2:])
        elif constraint.startswith("<="):
            return version <= ModuleVersion.parse(constraint[2:])
        elif constraint.startswith(">"):
            return version > ModuleVersion.parse(constraint[1:])
        elif constraint.startswith("<"):
            return version < ModuleVersion.parse(constraint[1:])
        elif constraint.startswith("==") or constraint.startswith("="):
            return version == ModuleVersion.parse(constraint.lstrip("="))
        else:
            # Exact version
            return version == ModuleVersion.parse(constraint)