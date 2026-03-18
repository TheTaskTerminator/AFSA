"""Permission models for RBAC."""
from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin, TimestampMixin
from app.models.types import JSONType


class Role(Base, UUIDMixin, TimestampMixin):
    """Role model for RBAC."""

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    permissions: Mapped[List[str]] = mapped_column(JSONType, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Permission(Base, UUIDMixin, TimestampMixin):
    """Permission model for fine-grained access control."""

    __tablename__ = "permissions"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    resource: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # read, write, delete, execute
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# Predefined roles
class RoleName:
    """Predefined role names."""

    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class PermissionName:
    """Predefined permission names."""

    # Task permissions
    TASK_READ = "task:read"
    TASK_WRITE = "task:write"
    TASK_DELETE = "task:delete"
    TASK_EXECUTE = "task:execute"

    # Conversation permissions
    CONVERSATION_READ = "conversation:read"
    CONVERSATION_WRITE = "conversation:write"
    CONVERSATION_DELETE = "conversation:delete"

    # Snapshot permissions
    SNAPSHOT_READ = "snapshot:read"
    SNAPSHOT_WRITE = "snapshot:write"
    SNAPSHOT_RESTORE = "snapshot:restore"

    # Audit permissions
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"

    # Admin permissions
    USER_MANAGE = "user:manage"
    ROLE_MANAGE = "role:manage"
    SYSTEM_CONFIG = "system:config"


# Role-Permission mappings
ROLE_PERMISSIONS: dict[str, List[str]] = {
    RoleName.ADMIN: [
        PermissionName.TASK_READ,
        PermissionName.TASK_WRITE,
        PermissionName.TASK_DELETE,
        PermissionName.TASK_EXECUTE,
        PermissionName.CONVERSATION_READ,
        PermissionName.CONVERSATION_WRITE,
        PermissionName.CONVERSATION_DELETE,
        PermissionName.SNAPSHOT_READ,
        PermissionName.SNAPSHOT_WRITE,
        PermissionName.SNAPSHOT_RESTORE,
        PermissionName.AUDIT_READ,
        PermissionName.AUDIT_EXPORT,
        PermissionName.USER_MANAGE,
        PermissionName.ROLE_MANAGE,
        PermissionName.SYSTEM_CONFIG,
    ],
    RoleName.DEVELOPER: [
        PermissionName.TASK_READ,
        PermissionName.TASK_WRITE,
        PermissionName.TASK_EXECUTE,
        PermissionName.CONVERSATION_READ,
        PermissionName.CONVERSATION_WRITE,
        PermissionName.SNAPSHOT_READ,
        PermissionName.SNAPSHOT_WRITE,
        PermissionName.AUDIT_READ,
    ],
    RoleName.VIEWER: [
        PermissionName.TASK_READ,
        PermissionName.CONVERSATION_READ,
        PermissionName.SNAPSHOT_READ,
    ],
}