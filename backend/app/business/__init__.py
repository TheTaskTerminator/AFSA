"""Business layer module.

This module provides framework-agnostic business logic definitions,
including models, APIs, and module management.
"""
from app.business.module import (
    BusinessModule,
    ModuleDependency,
    ModuleVersion,
)
from app.business.registry import (
    CircularDependencyError,
    DependencyNotSatisfiedError,
    ModuleNotFoundError,
    ModuleRegistry,
    ModuleRegistrationResult,
    get_module_registry,
    reset_module_registry,
)
from app.business.zone_config import (
    BUSINESS_ZONE_CONFIG,
    can_agent_modify,
    get_zone_for_file,
    initialize_business_zones,
    is_protected_path,
)

__all__ = [
    # Module management
    "BusinessModule",
    "ModuleVersion",
    "ModuleDependency",
    # Registry
    "ModuleRegistry",
    "ModuleRegistrationResult",
    "ModuleNotFoundError",
    "CircularDependencyError",
    "DependencyNotSatisfiedError",
    "get_module_registry",
    "reset_module_registry",
    # Zone configuration
    "BUSINESS_ZONE_CONFIG",
    "initialize_business_zones",
    "get_zone_for_file",
    "is_protected_path",
    "can_agent_modify",
]