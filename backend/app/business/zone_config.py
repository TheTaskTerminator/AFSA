"""Business layer zone configuration.

This module defines the zone configuration for the business layer,
including which areas are mutable (can be modified by Agent Team)
and which are immutable (protected from modification).
"""
from typing import Any, Dict

from app.governance.zone import ZoneConfig, ZoneType, get_zone_registry


# Default zone configuration for business layer
BUSINESS_ZONE_CONFIG: Dict[str, Any] = {
    "immutable": {
        "auth": {
            "path": ["app/business/immutable/auth", "/immutable/auth"],
            "description": "Core authentication logic - user verification, token management",
            "writable_by": ["admin"],
            "readable_by": ["admin", "developer", "viewer"],
        },
        "core": {
            "path": ["app/business/immutable/core", "/immutable/core"],
            "description": "Core system components - kernel functions, system APIs",
            "writable_by": ["admin"],
            "readable_by": ["admin", "developer", "viewer"],
        },
        "security": {
            "path": ["app/business/immutable/security", "/immutable/security"],
            "description": "Security policies - access control, encryption, audit",
            "writable_by": ["admin"],
            "readable_by": ["admin", "developer", "viewer"],
        },
        "config": {
            "path": ["app/business/immutable/config", "/immutable/config"],
            "description": "System configuration - environment, feature flags",
            "writable_by": ["admin"],
            "readable_by": ["admin", "developer", "viewer"],
        },
        "database": {
            "path": [
                "app/business/immutable/database",
                "/immutable/database",
                "app/models",  # Core data models
                "app/schemas",  # API schemas
            ],
            "description": "Core database models and API schemas",
            "writable_by": ["admin"],
            "readable_by": ["admin", "developer", "viewer"],
        },
        "governance": {
            "path": ["app/governance", "/governance"],
            "description": "Governance layer - permissions, audit, compliance",
            "writable_by": ["admin"],
            "readable_by": ["admin", "developer", "viewer"],
        },
        "orchestration": {
            "path": ["app/orchestration", "/orchestration"],
            "description": "Orchestration layer - dispatcher, sandbox, version control",
            "writable_by": ["admin"],
            "readable_by": ["admin", "developer", "viewer"],
        },
    },
    "mutable": {
        "rules": {
            "path": ["app/business/mutable/rules", "/mutable/rules"],
            "description": "Business rules - validation, calculation, workflow rules",
            "writable_by": ["admin", "developer"],
            "readable_by": ["admin", "developer", "viewer"],
        },
        "ui_config": {
            "path": ["app/business/mutable/ui_config", "/mutable/ui_config"],
            "description": "UI configuration - themes, layouts, component settings",
            "writable_by": ["admin", "developer"],
            "readable_by": ["admin", "developer", "viewer"],
        },
        "extensions": {
            "path": ["app/business/mutable/extensions", "/mutable/extensions"],
            "description": "Custom extensions and plugins",
            "writable_by": ["admin", "developer"],
            "readable_by": ["admin", "developer", "viewer"],
        },
        "api_endpoints": {
            "path": ["app/api/v1/endpoints", "/api/v1/endpoints"],
            "description": "API endpoints - can be extended with new endpoints",
            "writable_by": ["admin", "developer"],
            "readable_by": ["admin", "developer", "viewer"],
        },
        "agents": {
            "path": ["app/agents/pm_agent", "app/agents/frontend_agent", "app/agents/backend_agent"],
            "description": "Agent implementations - prompts, tools, configurations",
            "writable_by": ["admin", "developer"],
            "readable_by": ["admin", "developer", "viewer"],
        },
    },
}


def initialize_business_zones() -> None:
    """Initialize business layer zones.

    This should be called during application startup to register
    all business layer zones.
    """
    registry = get_zone_registry()
    registry.load_from_config(BUSINESS_ZONE_CONFIG)


def get_zone_for_file(file_path: str) -> str:
    """Get the zone name for a file path.

    Args:
        file_path: Path to check

    Returns:
        Zone name or 'unknown' if not in a registered zone
    """
    registry = get_zone_registry()
    result = registry.get_zone_for_path(file_path)

    if result.matched and result.zone_name:
        return result.zone_name

    return "unknown"


def is_protected_path(file_path: str) -> bool:
    """Check if a file path is in a protected (immutable) zone.

    Args:
        file_path: Path to check

    Returns:
        True if the path is protected
    """
    registry = get_zone_registry()
    return registry.is_immutable_path(file_path)


def can_agent_modify(file_path: str, agent_roles: set) -> bool:
    """Check if an agent with given roles can modify a file.

    Args:
        file_path: Path to check
        agent_roles: Set of roles the agent has

    Returns:
        True if modification is allowed
    """
    registry = get_zone_registry()
    return registry.can_write(file_path, agent_roles)