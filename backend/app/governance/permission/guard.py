"""Permission guard for RBAC + ABAC."""
from enum import Enum
from typing import List, Optional, Set

from app.models.permission import ROLE_PERMISSIONS, RoleName


class ActionType(str, Enum):
    """Action types for permission checks."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXECUTE = "execute"
    MANAGE = "manage"


class ZoneType(str, Enum):
    """Zone types for resource classification."""

    MUTABLE = "mutable"
    IMMUTABLE = "immutable"


# Immutable zone paths - write protected
IMMUTABLE_PATHS: Set[str] = {
    "/immutable/auth",
    "/immutable/core",
    "/immutable/security",
    "/immutable/config",
    "/immutable/database",
}


class PermissionDeniedError(Exception):
    """Permission denied error."""

    def __init__(
        self,
        action: str,
        resource: str,
        reason: Optional[str] = None,
    ):
        self.action = action
        self.resource = resource
        self.reason = reason
        super().__init__(
            f"Permission denied: {action} on {resource}"
            + (f" - {reason}" if reason else "")
        )


class PermissionGuard:
    """Permission guard for RBAC + ABAC hybrid model."""

    def __init__(self):
        # Role -> Permissions mapping
        self._role_permissions = ROLE_PERMISSIONS.copy()
        # User -> Roles mapping (can be extended to load from database)
        self._user_roles: dict[str, Set[str]] = {}
        # Permission cache (can be extended to use Redis)
        self._permission_cache: dict[str, Set[str]] = {}

    def get_permissions_for_role(self, role: str) -> Set[str]:
        """Get all permissions for a role."""
        return set(self._role_permissions.get(role, []))

    def get_permissions_for_user(self, user_id: str) -> Set[str]:
        """Get all permissions for a user."""
        if user_id in self._permission_cache:
            return self._permission_cache[user_id]

        permissions: Set[str] = set()
        for role in self._user_roles.get(user_id, set()):
            permissions.update(self.get_permissions_for_role(role))

        self._permission_cache[user_id] = permissions
        return permissions

    def assign_role(self, user_id: str, role: str) -> None:
        """Assign a role to a user."""
        if user_id not in self._user_roles:
            self._user_roles[user_id] = set()
        self._user_roles[user_id].add(role)
        # Invalidate cache
        self._permission_cache.pop(user_id, None)

    def revoke_role(self, user_id: str, role: str) -> None:
        """Revoke a role from a user."""
        if user_id in self._user_roles:
            self._user_roles[user_id].discard(role)
            # Invalidate cache
            self._permission_cache.pop(user_id, None)

    def check(
        self,
        user_id: str,
        action: ActionType,
        resource: str,
        zone: ZoneType = ZoneType.MUTABLE,
    ) -> bool:
        """Check if user has permission for action on resource."""
        # Check immutable zone protection
        if self._is_immutable_path(resource):
            if action in (ActionType.WRITE, ActionType.DELETE):
                # Only admin can write to immutable zone
                user_roles = self._user_roles.get(user_id, set())
                if RoleName.ADMIN not in user_roles:
                    return False
                # Admin can access immutable zone
                return True

        # Check RBAC permission
        permission = f"{resource}:{action.value}"
        user_permissions = self.get_permissions_for_user(user_id)

        # Check exact permission
        if permission in user_permissions:
            return True

        # Check wildcard permission (e.g., "task:*" matches "task:read")
        resource_prefix = f"{resource}:*"
        if resource_prefix in user_permissions:
            return True

        return False

    def check_or_raise(
        self,
        user_id: str,
        action: ActionType,
        resource: str,
        zone: ZoneType = ZoneType.MUTABLE,
    ) -> None:
        """Check permission and raise exception if denied."""
        if not self.check(user_id, action, resource, zone):
            raise PermissionDeniedError(
                action=action.value,
                resource=resource,
                reason=f"User {user_id} does not have {action.value} permission on {resource}",
            )

    def _is_immutable_path(self, path: str) -> bool:
        """Check if path is in immutable zone."""
        for immutable_path in IMMUTABLE_PATHS:
            if path.startswith(immutable_path):
                return True
        return False

    def clear_cache(self, user_id: Optional[str] = None) -> None:
        """Clear permission cache."""
        if user_id:
            self._permission_cache.pop(user_id, None)
        else:
            self._permission_cache.clear()


# Global permission guard instance
permission_guard = PermissionGuard()