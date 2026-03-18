"""Tests for permission guard."""
import pytest

from app.governance.permission import (
    PermissionGuard,
    PermissionDeniedError,
    ActionType,
    ZoneType,
    permission_guard,
    RoleName,
)


class TestPermissionGuard:
    """Tests for PermissionGuard."""

    def setup_method(self):
        """Set up test fixtures."""
        self.guard = PermissionGuard()

    def test_get_permissions_for_role(self):
        """Test getting permissions for predefined roles."""
        admin_perms = self.guard.get_permissions_for_role(RoleName.ADMIN)
        developer_perms = self.guard.get_permissions_for_role(RoleName.DEVELOPER)
        viewer_perms = self.guard.get_permissions_for_role(RoleName.VIEWER)

        # Admin should have most permissions
        assert len(admin_perms) > len(developer_perms)
        assert len(developer_perms) > len(viewer_perms)

    def test_assign_role(self):
        """Test assigning role to user."""
        self.guard.assign_role("user1", RoleName.DEVELOPER)
        permissions = self.guard.get_permissions_for_user("user1")

        assert "task:read" in permissions
        assert "task:write" in permissions

    def test_revoke_role(self):
        """Test revoking role from user."""
        self.guard.assign_role("user2", RoleName.DEVELOPER)
        self.guard.revoke_role("user2", RoleName.DEVELOPER)
        permissions = self.guard.get_permissions_for_user("user2")

        assert len(permissions) == 0

    def test_check_permission(self):
        """Test checking permission."""
        self.guard.assign_role("user3", RoleName.DEVELOPER)

        # Should have task:read
        assert self.guard.check("user3", ActionType.READ, "task")

        # Should not have user:manage (admin only)
        assert not self.guard.check("user3", ActionType.MANAGE, "user")

    def test_check_or_raise(self):
        """Test check_or_raise raises exception when denied."""
        self.guard.assign_role("user4", RoleName.VIEWER)

        # Should not raise for read permission
        self.guard.check_or_raise("user4", ActionType.READ, "task")

        # Should raise for write permission
        with pytest.raises(PermissionDeniedError) as exc_info:
            self.guard.check_or_raise("user4", ActionType.WRITE, "task")

        assert "Permission denied" in str(exc_info.value)

    def test_immutable_zone_protection(self):
        """Test immutable zone write protection."""
        self.guard.assign_role("user5", RoleName.DEVELOPER)

        # Developer cannot write to immutable zone
        assert not self.guard.check(
            "user5",
            ActionType.WRITE,
            "/immutable/auth/config",
            ZoneType.IMMUTABLE,
        )

        # Admin can write to immutable zone
        self.guard.assign_role("admin1", RoleName.ADMIN)
        assert self.guard.check(
            "admin1",
            ActionType.WRITE,
            "/immutable/auth/config",
            ZoneType.IMMUTABLE,
        )

    def test_cache_invalidation(self):
        """Test permission cache invalidation."""
        self.guard.assign_role("user6", RoleName.VIEWER)
        permissions1 = self.guard.get_permissions_for_user("user6")

        self.guard.assign_role("user6", RoleName.DEVELOPER)
        self.guard.clear_cache("user6")
        permissions2 = self.guard.get_permissions_for_user("user6")

        # After role change and cache clear, permissions should be different
        assert len(permissions2) > len(permissions1)


class TestPermissionDeniedError:
    """Tests for PermissionDeniedError."""

    def test_error_message(self):
        """Test error message format."""
        error = PermissionDeniedError(
            action="write",
            resource="task",
            reason="Insufficient permissions",
        )

        assert "write" in str(error)
        assert "task" in str(error)
        assert "Insufficient permissions" in str(error)