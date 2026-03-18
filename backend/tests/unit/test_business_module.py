"""Tests for business module and registry."""
import pytest

from app.business import (
    BusinessModule,
    ModuleDependency,
    ModuleVersion,
    ModuleRegistry,
    ModuleRegistrationResult,
    ModuleNotFoundError,
    CircularDependencyError,
    DependencyNotSatisfiedError,
    get_module_registry,
    reset_module_registry,
)
from app.business.dsl import (
    BusinessModel,
    APIInterface,
    id_field,
    name_field,
    email_field,
    created_at_field,
    updated_at_field,
    list_endpoint,
    get_endpoint,
)
from app.governance.zone import ZoneType


class TestModuleVersion:
    """Tests for ModuleVersion."""

    def test_parse_simple_version(self):
        """Test parsing simple version."""
        version = ModuleVersion.parse("1.2.3")

        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.prerelease is None

    def test_parse_prerelease_version(self):
        """Test parsing prerelease version."""
        version = ModuleVersion.parse("1.2.3-alpha")

        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3
        assert version.prerelease == "alpha"

    def test_parse_partial_version(self):
        """Test parsing partial version."""
        version = ModuleVersion.parse("1")

        assert version.major == 1
        assert version.minor == 0
        assert version.patch == 0

    def test_version_comparison(self):
        """Test version comparison."""
        v1 = ModuleVersion.parse("1.0.0")
        v2 = ModuleVersion.parse("2.0.0")
        v3 = ModuleVersion.parse("1.1.0")
        v4 = ModuleVersion.parse("1.0.1")

        assert v1 < v2
        assert v1 < v3
        assert v1 < v4
        assert v2 > v3
        assert v3 > v4

    def test_prerelease_comparison(self):
        """Test prerelease version comparison."""
        v1 = ModuleVersion.parse("1.0.0-alpha")
        v2 = ModuleVersion.parse("1.0.0-beta")
        v3 = ModuleVersion.parse("1.0.0")

        assert v1 < v2
        assert v2 < v3  # prerelease < release
        assert v3 > v1

    def test_version_string(self):
        """Test version string representation."""
        version = ModuleVersion.parse("1.2.3-alpha")
        assert str(version) == "1.2.3-alpha"


class TestModuleDependency:
    """Tests for ModuleDependency."""

    def test_no_constraint(self):
        """Test dependency without version constraint."""
        dep = ModuleDependency(module_id="test-module")

        assert dep.is_satisfied_by(ModuleVersion.parse("1.0.0"))
        assert dep.is_satisfied_by(ModuleVersion.parse("999.999.999"))

    def test_exact_version(self):
        """Test exact version constraint."""
        dep = ModuleDependency(module_id="test-module", version_constraint="1.2.3")

        assert dep.is_satisfied_by(ModuleVersion.parse("1.2.3"))
        assert not dep.is_satisfied_by(ModuleVersion.parse("1.2.4"))

    def test_gte_constraint(self):
        """Test >= constraint."""
        dep = ModuleDependency(module_id="test-module", version_constraint=">=1.0.0")

        assert dep.is_satisfied_by(ModuleVersion.parse("1.0.0"))
        assert dep.is_satisfied_by(ModuleVersion.parse("2.0.0"))
        assert not dep.is_satisfied_by(ModuleVersion.parse("0.9.9"))

    def test_range_constraint(self):
        """Test range constraint."""
        dep = ModuleDependency(
            module_id="test-module", version_constraint=">=1.0.0,<2.0.0"
        )

        assert dep.is_satisfied_by(ModuleVersion.parse("1.0.0"))
        assert dep.is_satisfied_by(ModuleVersion.parse("1.9.9"))
        assert not dep.is_satisfied_by(ModuleVersion.parse("2.0.0"))
        assert not dep.is_satisfied_by(ModuleVersion.parse("0.9.9"))


class TestBusinessModule:
    """Tests for BusinessModule."""

    def test_basic_module(self):
        """Test creating a basic module."""
        module = BusinessModule(
            id="user-management",
            name="User Management",
            description="User management functionality",
        )

        assert module.id == "user-management"
        assert module.name == "User Management"
        assert module.version == "1.0.0"
        assert module.zone == ZoneType.MUTABLE
        assert module.enabled is True
        assert len(module.models) == 0
        assert len(module.apis) == 0

    def test_module_with_models(self):
        """Test module with models."""
        user_model = (
            BusinessModel(name="User", table_name="users")
            .add_field(id_field())
            .add_field(name_field())
            .add_field(email_field())
        )

        module = BusinessModule(
            id="user-management",
            name="User Management",
            models=[user_model],
        )

        assert len(module.models) == 1
        assert module.get_model("User") is not None
        assert module.get_model("NonExistent") is None

    def test_module_with_apis(self):
        """Test module with APIs."""
        user_api = APIInterface(
            name="UserAPI",
            base_path="/api/v1/users",
            endpoints=[
                list_endpoint("users", "/api/v1/users", {"type": "array"}),
            ],
        )

        module = BusinessModule(
            id="user-management",
            name="User Management",
            apis=[user_api],
        )

        assert len(module.apis) == 1
        assert module.get_api("UserAPI") is not None

    def test_module_fluent_api(self):
        """Test fluent API for building modules."""
        model = BusinessModel(name="Post", table_name="posts").add_field(id_field())

        module = (
            BusinessModule(id="blog", name="Blog")
            .add_model(model)
            .add_dependency("user-management")
            .add_api(
                APIInterface(
                    name="PostAPI",
                    base_path="/api/v1/posts",
                    endpoints=[],
                )
            )
        )

        assert len(module.models) == 1
        assert len(module.apis) == 1
        assert "user-management" in module.dependencies

    def test_module_to_dict(self):
        """Test module serialization."""
        module = BusinessModule(
            id="test",
            name="Test Module",
            version="2.0.0",
            tags=["core", "testing"],
        )

        data = module.to_dict()

        assert data["id"] == "test"
        assert data["name"] == "Test Module"
        assert data["version"] == "2.0.0"
        assert "core" in data["tags"]


class TestModuleRegistry:
    """Tests for ModuleRegistry."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up fresh registry for each test."""
        reset_module_registry()
        self.registry = get_module_registry()
        yield
        reset_module_registry()

    def test_register_module(self):
        """Test registering a module."""
        module = BusinessModule(id="test", name="Test Module")

        result = self.registry.register(module)

        assert result.success
        assert result.module_id == "test"
        assert self.registry.get("test") == module

    def test_register_duplicate_module(self):
        """Test registering duplicate module."""
        module1 = BusinessModule(id="test", name="Test 1")
        module2 = BusinessModule(id="test", name="Test 2")

        result1 = self.registry.register(module1)
        result2 = self.registry.register(module2)

        assert result1.success
        assert not result2.success
        assert "already registered" in result2.message

    def test_unregister_module(self):
        """Test unregistering a module."""
        module = BusinessModule(id="test", name="Test")
        self.registry.register(module)

        result = self.registry.unregister("test")

        assert result is True
        assert self.registry.get("test") is None

    def test_unregister_nonexistent(self):
        """Test unregistering nonexistent module."""
        with pytest.raises(ModuleNotFoundError):
            self.registry.unregister("nonexistent")

    def test_unregister_with_dependents(self):
        """Test unregistering module with dependents."""
        core = BusinessModule(id="core", name="Core")
        plugin = BusinessModule(
            id="plugin",
            name="Plugin",
            dependencies=["core"],
        )

        self.registry.register(core)
        self.registry.register(plugin)

        with pytest.raises(Exception):  # ModuleRegistryError
            self.registry.unregister("core")

    def test_get_by_model(self):
        """Test getting module by model name."""
        model = BusinessModel(name="User", table_name="users").add_field(id_field())
        module = BusinessModule(id="users", name="Users", models=[model])

        self.registry.register(module)

        found = self.registry.get_by_model("User")
        assert found == module

    def test_get_by_api(self):
        """Test getting module by API name."""
        api = APIInterface(name="UserAPI", base_path="/users", endpoints=[])
        module = BusinessModule(id="users", name="Users", apis=[api])

        self.registry.register(module)

        found = self.registry.get_by_api("UserAPI")
        assert found == module

    def test_list_all(self):
        """Test listing all modules."""
        m1 = BusinessModule(id="m1", name="Module 1")
        m2 = BusinessModule(id="m2", name="Module 2")

        self.registry.register(m1)
        self.registry.register(m2)

        modules = self.registry.list_all()
        assert len(modules) == 2

    def test_list_by_zone(self):
        """Test listing modules by zone."""
        mutable = BusinessModule(id="mutable", name="Mutable", zone=ZoneType.MUTABLE)
        immutable = BusinessModule(
            id="immutable", name="Immutable", zone=ZoneType.IMMUTABLE
        )

        self.registry.register(mutable)
        self.registry.register(immutable)

        mutable_modules = self.registry.list_by_zone(ZoneType.MUTABLE)
        assert len(mutable_modules) == 1
        assert mutable_modules[0].id == "mutable"

    def test_search(self):
        """Test searching modules."""
        module = BusinessModule(
            id="user-mgmt",
            name="User Management",
            description="Manage users and permissions",
            tags=["core", "auth"],
        )

        self.registry.register(module)

        results = self.registry.search("user")
        assert len(results) == 1

        results = self.registry.search("auth")
        assert len(results) == 1

        results = self.registry.search("nonexistent")
        assert len(results) == 0

    def test_dependency_order(self):
        """Test getting dependency order."""
        core = BusinessModule(id="core", name="Core")
        auth = BusinessModule(
            id="auth",
            name="Auth",
            dependencies=["core"],
        )
        api = BusinessModule(
            id="api",
            name="API",
            dependencies=["auth", "core"],
        )

        self.registry.register(core)
        self.registry.register(auth)
        self.registry.register(api)

        order = self.registry.get_dependency_order()

        # Core should come before auth
        assert order.index("core") < order.index("auth")
        # Auth should come before api
        assert order.index("auth") < order.index("api")

    def test_enable_disable(self):
        """Test enabling and disabling modules."""
        module = BusinessModule(id="test", name="Test", enabled=False)
        self.registry.register(module)

        assert not module.enabled

        self.registry.enable("test")
        assert module.enabled

        self.registry.disable("test")
        assert not module.enabled

    def test_circular_dependency_detection(self):
        """Test circular dependency detection."""
        a = BusinessModule(id="a", name="A", dependencies=["c"])
        b = BusinessModule(id="b", name="B", dependencies=["a"])
        c = BusinessModule(id="c", name="C", dependencies=["b"])

        self.registry.register(a)
        self.registry.register(b)

        # Registering c would create a cycle
        result = self.registry.register(c)
        assert not result.success
        assert "Circular" in result.message

    def test_hooks(self):
        """Test lifecycle hooks."""
        called = []

        def on_register(m):
            called.append(("register", m.id))

        def on_enable(m):
            called.append(("enable", m.id))

        self.registry.add_hook("post_register", on_register)
        self.registry.add_hook("post_enable", on_enable)

        # Create a disabled module to test enable hook
        module = BusinessModule(id="test", name="Test", enabled=False)
        self.registry.register(module)

        # Module is disabled, enable it to trigger hook
        self.registry.enable("test")

        assert ("register", "test") in called
        assert ("enable", "test") in called

    def test_get_all_models(self):
        """Test getting all models from all modules."""
        model1 = BusinessModel(name="User", table_name="users").add_field(id_field())
        model2 = BusinessModel(name="Post", table_name="posts").add_field(id_field())

        m1 = BusinessModule(id="users", name="Users", models=[model1])
        m2 = BusinessModule(id="posts", name="Posts", models=[model2], enabled=False)

        self.registry.register(m1)
        self.registry.register(m2)

        all_models = self.registry.get_all_models()
        assert len(all_models) == 1  # Only enabled modules
        assert all_models[0].name == "User"

    def test_validate_dependencies(self):
        """Test validating dependencies."""
        module = BusinessModule(
            id="test",
            name="Test",
            dependencies=["nonexistent1", "nonexistent2"],
        )

        self.registry.register(module)
        issues = self.registry.validate_dependencies()

        assert "test" in issues
        assert "nonexistent1" in issues["test"]
        assert "nonexistent2" in issues["test"]