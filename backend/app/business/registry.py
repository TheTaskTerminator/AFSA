"""Business module registry.

This module provides the registry for business modules, supporting
registration, discovery, dependency resolution, and lifecycle management.
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from app.business.dsl import APIInterface, BusinessModel
from app.business.module import BusinessModule, ModuleVersion, ModuleDependency
from app.governance.zone import ZoneType

logger = logging.getLogger(__name__)


class ModuleRegistryError(Exception):
    """Base exception for module registry errors."""
    pass


class ModuleNotFoundError(ModuleRegistryError):
    """Raised when a module is not found."""
    pass


class CircularDependencyError(ModuleRegistryError):
    """Raised when circular dependencies are detected."""
    pass


class DependencyNotSatisfiedError(ModuleRegistryError):
    """Raised when a dependency is not satisfied."""
    pass


@dataclass
class ModuleRegistrationResult:
    """Result of a module registration attempt."""

    success: bool
    module_id: str
    message: str
    warnings: List[str] = field(default_factory=list)


class ModuleRegistry:
    """Registry for business modules.

    Provides functionality for:
    - Module registration and unregistration
    - Module discovery by various criteria
    - Dependency resolution
    - Lifecycle management (enable/disable)
    """

    def __init__(self):
        self._modules: Dict[str, BusinessModule] = {}
        self._model_index: Dict[str, str] = {}  # model_name -> module_id
        self._api_index: Dict[str, str] = {}  # api_name -> module_id
        self._hooks: Dict[str, List[Callable]] = {
            "pre_register": [],
            "post_register": [],
            "pre_unregister": [],
            "post_unregister": [],
            "pre_enable": [],
            "post_enable": [],
            "pre_disable": [],
            "post_disable": [],
        }

    def register(self, module: BusinessModule) -> ModuleRegistrationResult:
        """Register a business module.

        Args:
            module: Module to register

        Returns:
            Registration result with success status and messages
        """
        warnings = []

        # Run pre-register hooks
        for hook in self._hooks["pre_register"]:
            try:
                hook(module)
            except Exception as e:
                logger.warning(f"Pre-register hook failed: {e}")

        # Check if already registered
        if module.id in self._modules:
            return ModuleRegistrationResult(
                success=False,
                module_id=module.id,
                message=f"Module '{module.id}' is already registered",
            )

        # Validate dependencies
        missing_deps = []
        for dep_id in module.dependencies:
            if dep_id not in self._modules:
                missing_deps.append(dep_id)

        if missing_deps:
            warnings.append(
                f"Missing dependencies: {', '.join(missing_deps)}. "
                "Module will be registered but may not function correctly."
            )

        # Check for circular dependencies
        cycle = self._detect_circular_dependency(module)
        if cycle:
            return ModuleRegistrationResult(
                success=False,
                module_id=module.id,
                message=f"Circular dependency detected: {' -> '.join(cycle)}",
            )

        # Register module
        self._modules[module.id] = module

        # Build indexes
        for model in module.models:
            self._model_index[model.name] = module.id

        for api in module.apis:
            self._api_index[api.name] = module.id

        # Run post-register hooks
        for hook in self._hooks["post_register"]:
            try:
                hook(module)
            except Exception as e:
                logger.warning(f"Post-register hook failed: {e}")

        message = f"Module '{module.id}' v{module.version} registered successfully"
        if warnings:
            message += f" (with {len(warnings)} warning(s))"

        logger.info(message)

        return ModuleRegistrationResult(
            success=True,
            module_id=module.id,
            message=message,
            warnings=warnings,
        )

    def unregister(self, module_id: str) -> bool:
        """Unregister a module.

        Args:
            module_id: ID of module to unregister

        Returns:
            True if unregistered successfully

        Raises:
            ModuleNotFoundError: If module not found
        """
        if module_id not in self._modules:
            raise ModuleNotFoundError(f"Module '{module_id}' not found")

        module = self._modules[module_id]

        # Check if other modules depend on this one
        dependents = self.get_dependents(module_id)
        if dependents:
            raise ModuleRegistryError(
                f"Cannot unregister: modules {dependents} depend on '{module_id}'"
            )

        # Run pre-unregister hooks
        for hook in self._hooks["pre_unregister"]:
            try:
                hook(module)
            except Exception as e:
                logger.warning(f"Pre-unregister hook failed: {e}")

        # Remove from indexes
        for model in module.models:
            self._model_index.pop(model.name, None)

        for api in module.apis:
            self._api_index.pop(api.name, None)

        # Remove module
        del self._modules[module_id]

        # Run post-unregister hooks
        for hook in self._hooks["post_unregister"]:
            try:
                hook(module)
            except Exception as e:
                logger.warning(f"Post-unregister hook failed: {e}")

        logger.info(f"Module '{module_id}' unregistered")
        return True

    def get(self, module_id: str) -> Optional[BusinessModule]:
        """Get a module by ID.

        Args:
            module_id: Module ID

        Returns:
            BusinessModule if found, None otherwise
        """
        return self._modules.get(module_id)

    def get_by_model(self, model_name: str) -> Optional[BusinessModule]:
        """Get the module that owns a model.

        Args:
            model_name: Name of the model

        Returns:
            BusinessModule if found, None otherwise
        """
        module_id = self._model_index.get(model_name)
        if module_id:
            return self._modules.get(module_id)
        return None

    def get_by_api(self, api_name: str) -> Optional[BusinessModule]:
        """Get the module that owns an API.

        Args:
            api_name: Name of the API

        Returns:
            BusinessModule if found, None otherwise
        """
        module_id = self._api_index.get(api_name)
        if module_id:
            return self._modules.get(module_id)
        return None

    def list_all(self) -> List[BusinessModule]:
        """List all registered modules.

        Returns:
            List of all modules
        """
        return list(self._modules.values())

    def list_enabled(self) -> List[BusinessModule]:
        """List all enabled modules.

        Returns:
            List of enabled modules
        """
        return [m for m in self._modules.values() if m.enabled]

    def list_by_zone(self, zone: ZoneType) -> List[BusinessModule]:
        """List modules by zone type.

        Args:
            zone: Zone type to filter by

        Returns:
            List of modules in the specified zone
        """
        return [m for m in self._modules.values() if m.zone == zone]

    def find_by_tag(self, tag: str) -> List[BusinessModule]:
        """Find modules by tag.

        Args:
            tag: Tag to search for

        Returns:
            List of modules with the specified tag
        """
        return [m for m in self._modules.values() if tag in m.tags]

    def find_by_author(self, author: str) -> List[BusinessModule]:
        """Find modules by author.

        Args:
            author: Author name to search for

        Returns:
            List of modules by the specified author
        """
        return [m for m in self._modules.values() if m.author == author]

    def search(self, query: str) -> List[BusinessModule]:
        """Search modules by name, description, or tags.

        Args:
            query: Search query

        Returns:
            List of matching modules
        """
        query = query.lower()
        results = []

        for module in self._modules.values():
            if (
                query in module.name.lower()
                or query in module.description.lower()
                or query in module.id.lower()
                or any(query in tag.lower() for tag in module.tags)
            ):
                results.append(module)

        return results

    def get_dependencies(self, module_id: str) -> List[BusinessModule]:
        """Get direct dependencies of a module.

        Args:
            module_id: Module ID

        Returns:
            List of dependency modules
        """
        module = self.get(module_id)
        if not module:
            return []

        deps = []
        for dep_id in module.dependencies:
            dep = self.get(dep_id)
            if dep:
                deps.append(dep)

        return deps

    def get_dependents(self, module_id: str) -> List[str]:
        """Get modules that depend on a given module.

        Args:
            module_id: Module ID

        Returns:
            List of module IDs that depend on this module
        """
        dependents = []
        for mid, module in self._modules.items():
            if module_id in module.dependencies:
                dependents.append(mid)
        return dependents

    def get_dependency_order(self) -> List[str]:
        """Get all modules in dependency order (topological sort).

        Returns:
            List of module IDs in order (dependencies first)
        """
        visited = set()
        order = []

        def visit(module_id: str):
            if module_id in visited:
                return
            visited.add(module_id)

            module = self.get(module_id)
            if module:
                for dep_id in module.dependencies:
                    if dep_id in self._modules:
                        visit(dep_id)

            order.append(module_id)

        for module_id in self._modules:
            visit(module_id)

        return order

    def enable(self, module_id: str) -> bool:
        """Enable a module.

        Args:
            module_id: Module ID

        Returns:
            True if enabled successfully
        """
        module = self.get(module_id)
        if not module:
            raise ModuleNotFoundError(f"Module '{module_id}' not found")

        if module.enabled:
            return True

        # Check dependencies are enabled
        for dep_id in module.dependencies:
            dep = self.get(dep_id)
            if dep and not dep.enabled:
                raise DependencyNotSatisfiedError(
                    f"Dependency '{dep_id}' is not enabled"
                )

        # Run pre-enable hooks
        for hook in self._hooks["pre_enable"]:
            try:
                hook(module)
            except Exception as e:
                logger.warning(f"Pre-enable hook failed: {e}")

        module.enabled = True

        # Run post-enable hooks
        for hook in self._hooks["post_enable"]:
            try:
                hook(module)
            except Exception as e:
                logger.warning(f"Post-enable hook failed: {e}")

        logger.info(f"Module '{module_id}' enabled")
        return True

    def disable(self, module_id: str) -> bool:
        """Disable a module.

        Args:
            module_id: Module ID

        Returns:
            True if disabled successfully
        """
        module = self.get(module_id)
        if not module:
            raise ModuleNotFoundError(f"Module '{module_id}' not found")

        if not module.enabled:
            return True

        # Check if other enabled modules depend on this one
        enabled_dependents = [
            mid
            for mid in self.get_dependents(module_id)
            if self._modules[mid].enabled
        ]
        if enabled_dependents:
            raise ModuleRegistryError(
                f"Cannot disable: enabled modules {enabled_dependents} depend on '{module_id}'"
            )

        # Run pre-disable hooks
        for hook in self._hooks["pre_disable"]:
            try:
                hook(module)
            except Exception as e:
                logger.warning(f"Pre-disable hook failed: {e}")

        module.enabled = False

        # Run post-disable hooks
        for hook in self._hooks["post_disable"]:
            try:
                hook(module)
            except Exception as e:
                logger.warning(f"Post-disable hook failed: {e}")

        logger.info(f"Module '{module_id}' disabled")
        return True

    def add_hook(self, event: str, hook: Callable) -> None:
        """Add a lifecycle hook.

        Args:
            event: Event name (pre_register, post_register, etc.)
            hook: Callable to run on event
        """
        if event in self._hooks:
            self._hooks[event].append(hook)

    def remove_hook(self, event: str, hook: Callable) -> None:
        """Remove a lifecycle hook.

        Args:
            event: Event name
            hook: Hook to remove
        """
        if event in self._hooks and hook in self._hooks[event]:
            self._hooks[event].remove(hook)

    def get_all_models(self) -> List[BusinessModel]:
        """Get all models from all enabled modules.

        Returns:
            List of all business models
        """
        models = []
        for module in self.list_enabled():
            models.extend(module.models)
        return models

    def get_all_apis(self) -> List[APIInterface]:
        """Get all APIs from all enabled modules.

        Returns:
            List of all API interfaces
        """
        apis = []
        for module in self.list_enabled():
            apis.extend(module.apis)
        return apis

    def validate_dependencies(self) -> Dict[str, List[str]]:
        """Validate all module dependencies.

        Returns:
            Dictionary mapping module IDs to their missing dependencies
        """
        issues = {}
        for module_id, module in self._modules.items():
            missing = []
            for dep_id in module.dependencies:
                if dep_id not in self._modules:
                    missing.append(dep_id)
            if missing:
                issues[module_id] = missing
        return issues

    def _detect_circular_dependency(self, module: BusinessModule) -> Optional[List[str]]:
        """Detect if adding a module would create a circular dependency.

        Args:
            module: Module to check

        Returns:
            List representing the cycle if found, None otherwise
        """
        visited = set()
        path = []

        def visit(current_id: str, check_for: str) -> Optional[List[str]]:
            if current_id == check_for:
                # Found a path back to the module being registered
                return path + [current_id]

            if current_id in path:
                # Already in current path - this shouldn't happen
                # with proper dependency checking, but handle it
                return None

            if current_id in visited:
                return None

            visited.add(current_id)
            path.append(current_id)

            current = self._modules.get(current_id)
            if current:
                for dep_id in current.dependencies:
                    result = visit(dep_id, check_for)
                    if result:
                        return result

            path.pop()
            return None

        # For each dependency, check if it eventually leads back to this module
        # We do this by checking if any dependency chain leads to a module
        # that has this module as a dependency
        for dep_id in module.dependencies:
            # Reset for each starting dependency
            visited.clear()
            path.clear()

            # Check if this dependency leads back to the new module
            result = visit(dep_id, module.id)
            if result:
                return [module.id] + result

        # Also check if any existing module's dependency chain leads to this module
        # and this module's dependencies would close the loop
        for existing_id, existing_module in self._modules.items():
            visited.clear()
            path.clear()

            # Check if existing module depends on the new module
            if module.id in existing_module.dependencies:
                # Check if new module's dependencies lead to existing module
                for dep_id in module.dependencies:
                    result = visit(dep_id, existing_id)
                    if result:
                        return [module.id] + result

        return None

    def to_dict(self) -> Dict[str, Any]:
        """Export registry state as dictionary.

        Returns:
            Dictionary representation of registry
        """
        return {
            "modules": {mid: m.to_dict() for mid, m in self._modules.items()},
            "model_index": dict(self._model_index),
            "api_index": dict(self._api_index),
        }


# Global registry instance
_registry: Optional[ModuleRegistry] = None


def get_module_registry() -> ModuleRegistry:
    """Get the global module registry.

    Returns:
        ModuleRegistry singleton instance
    """
    global _registry
    if _registry is None:
        _registry = ModuleRegistry()
    return _registry


def reset_module_registry() -> None:
    """Reset the global module registry.

    Mainly for testing purposes.
    """
    global _registry
    _registry = None