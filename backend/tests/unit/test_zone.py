"""Tests for zone registry and configuration."""
import pytest

from app.governance.zone import (
    ZoneConfig,
    ZoneRegistry,
    ZoneType,
    get_zone_registry,
    initialize_zones,
)
from app.business.zone_config import (
    BUSINESS_ZONE_CONFIG,
    can_agent_modify,
    get_zone_for_file,
    initialize_business_zones,
    is_protected_path,
)


class TestZoneConfig:
    """Tests for ZoneConfig."""

    def test_zone_config_creation(self):
        """Test creating a zone configuration."""
        config = ZoneConfig(
            name="test",
            zone_type=ZoneType.IMMUTABLE,
            paths=["/test/path"],
            description="Test zone",
        )

        assert config.name == "test"
        assert config.zone_type == ZoneType.IMMUTABLE
        assert config.paths == ["/test/path"]
        assert config.description == "Test zone"

    def test_path_normalization(self):
        """Test path normalization."""
        config = ZoneConfig(
            name="test",
            zone_type=ZoneType.MUTABLE,
            paths=["test/path/", "/another/path/"],
        )

        # Should be normalized: leading slash, no trailing slash
        assert config.paths == ["/test/path", "/another/path"]

    def test_default_permissions(self):
        """Test default permission settings."""
        config = ZoneConfig(
            name="test",
            zone_type=ZoneType.IMMUTABLE,
            paths=["/test"],
        )

        # Default: only admin can write immutable
        assert config.writable_by == ["admin"]
        assert "admin" in config.readable_by


class TestZoneRegistry:
    """Tests for ZoneRegistry."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        reg = ZoneRegistry()
        yield reg

    def test_register_zone(self, registry):
        """Test registering a zone."""
        config = ZoneConfig(
            name="auth",
            zone_type=ZoneType.IMMUTABLE,
            paths=["/auth"],
        )

        registry.register_zone(config)

        assert registry.get_zone("auth") is not None

    def test_register_duplicate_zone(self, registry):
        """Test that duplicate zone names are rejected."""
        config = ZoneConfig(
            name="test",
            zone_type=ZoneType.MUTABLE,
            paths=["/test"],
        )

        registry.register_zone(config)

        with pytest.raises(ValueError, match="already registered"):
            registry.register_zone(config)

    def test_unregister_zone(self, registry):
        """Test unregistering a zone."""
        config = ZoneConfig(
            name="test",
            zone_type=ZoneType.MUTABLE,
            paths=["/test"],
        )

        registry.register_zone(config)
        assert registry.unregister_zone("test") is True
        assert registry.get_zone("test") is None

    def test_unregister_nonexistent(self, registry):
        """Test unregistering a non-existent zone."""
        assert registry.unregister_zone("nonexistent") is False

    def test_get_zone_for_path_exact_match(self, registry):
        """Test exact path matching."""
        registry.register_zone(ZoneConfig(
            name="auth",
            zone_type=ZoneType.IMMUTABLE,
            paths=["/auth"],
        ))

        result = registry.get_zone_for_path("/auth")

        assert result.matched is True
        assert result.zone_name == "auth"
        assert result.zone_type == ZoneType.IMMUTABLE

    def test_get_zone_for_path_prefix_match(self, registry):
        """Test prefix path matching."""
        registry.register_zone(ZoneConfig(
            name="auth",
            zone_type=ZoneType.IMMUTABLE,
            paths=["/auth"],
        ))

        result = registry.get_zone_for_path("/auth/users/login.py")

        assert result.matched is True
        assert result.zone_name == "auth"

    def test_get_zone_for_path_no_match(self, registry):
        """Test when no zone matches."""
        result = registry.get_zone_for_path("/unknown/path")

        assert result.matched is False
        assert result.zone_type == ZoneType.MUTABLE  # Default

    def test_is_immutable_path(self, registry):
        """Test immutable path checking."""
        registry.register_zone(ZoneConfig(
            name="core",
            zone_type=ZoneType.IMMUTABLE,
            paths=["/core"],
        ))
        registry.register_zone(ZoneConfig(
            name="rules",
            zone_type=ZoneType.MUTABLE,
            paths=["/rules"],
        ))

        assert registry.is_immutable_path("/core/config.py") is True
        assert registry.is_immutable_path("/rules/business.py") is False

    def test_can_write(self, registry):
        """Test write permission checking."""
        registry.register_zone(ZoneConfig(
            name="core",
            zone_type=ZoneType.IMMUTABLE,
            paths=["/core"],
            writable_by=["admin"],
        ))
        registry.register_zone(ZoneConfig(
            name="rules",
            zone_type=ZoneType.MUTABLE,
            paths=["/rules"],
            writable_by=["admin", "developer"],
        ))

        # Admin can write to both
        assert registry.can_write("/core/config.py", {"admin"}) is True
        assert registry.can_write("/rules/business.py", {"admin"}) is True

        # Developer can only write to mutable
        assert registry.can_write("/core/config.py", {"developer"}) is False
        assert registry.can_write("/rules/business.py", {"developer"}) is True

    def test_load_from_config(self, registry):
        """Test loading zones from configuration dict."""
        config = {
            "immutable": {
                "auth": {
                    "path": ["/auth"],
                    "description": "Authentication",
                },
            },
            "mutable": {
                "rules": {
                    "path": ["/rules"],
                    "description": "Business rules",
                },
            },
        }

        count = registry.load_from_config(config)

        assert count == 2
        assert registry.get_zone("auth") is not None
        assert registry.get_zone("rules") is not None


class TestGlobalRegistry:
    """Tests for global registry functions."""

    def test_get_zone_registry_singleton(self):
        """Test that get_zone_registry returns singleton."""
        registry1 = get_zone_registry()
        registry2 = get_zone_registry()

        assert registry1 is registry2

    def test_initialize_zones(self):
        """Test zone initialization."""
        config = {
            "immutable": {
                "test": {"path": ["/test"]},
            },
        }

        registry = initialize_zones(config)

        assert registry.get_zone("test") is not None


class TestBusinessZoneConfig:
    """Tests for business zone configuration."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Initialize business zones before each test."""
        registry = get_zone_registry()
        registry.clear()
        initialize_business_zones()

    def test_business_zones_loaded(self):
        """Test that business zones are loaded."""
        registry = get_zone_registry()

        # Should have immutable zones
        assert registry.get_zone("auth") is not None
        assert registry.get_zone("core") is not None
        assert registry.get_zone("security") is not None

        # Should have mutable zones
        assert registry.get_zone("rules") is not None
        assert registry.get_zone("ui_config") is not None

    def test_get_zone_for_file(self):
        """Test get_zone_for_file helper."""
        zone = get_zone_for_file("app/business/immutable/auth/user.py")
        assert zone == "auth"

        zone = get_zone_for_file("app/business/mutable/rules/validation.py")
        assert zone == "rules"

    def test_is_protected_path(self):
        """Test is_protected_path helper."""
        assert is_protected_path("app/business/immutable/auth") is True
        assert is_protected_path("app/business/mutable/rules") is False
        assert is_protected_path("app/governance/permission") is True

    def test_can_agent_modify(self):
        """Test can_agent_modify helper."""
        # Admin can modify anything
        assert can_agent_modify("app/business/immutable/auth", {"admin"}) is True
        assert can_agent_modify("app/business/mutable/rules", {"admin"}) is True

        # Developer can only modify mutable zones
        assert can_agent_modify("app/business/immutable/auth", {"developer"}) is False
        assert can_agent_modify("app/business/mutable/rules", {"developer"}) is True

        # Viewer cannot modify anything
        assert can_agent_modify("app/business/mutable/rules", {"viewer"}) is False

    def test_models_are_protected(self):
        """Test that core models are in protected zone."""
        assert is_protected_path("app/models/user.py") is True
        assert is_protected_path("app/schemas/task.py") is True

    def test_api_endpoints_are_mutable(self):
        """Test that API endpoints are in mutable zone."""
        assert is_protected_path("app/api/v1/endpoints/tasks.py") is False

    def test_governance_is_protected(self):
        """Test that governance layer is protected."""
        assert is_protected_path("app/governance/permission/guard.py") is True

    def test_orchestration_is_protected(self):
        """Test that orchestration layer is protected."""
        assert is_protected_path("app/orchestration/dispatcher/dispatcher.py") is True