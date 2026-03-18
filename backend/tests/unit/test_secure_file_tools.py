"""Tests for secure file tools with zone and permission checking."""
import os
import tempfile
from pathlib import Path

import pytest

from app.agents.tools.secure_file_tools import (
    SecureFileContext,
    SecureFileReadTool,
    SecureFileWriteTool,
    SecureFileDeleteTool,
    ZoneInfoTool,
    create_secure_file_tools,
)
from app.governance.zone import ZoneConfig, ZoneType, get_zone_registry


class TestSecureFileContext:
    """Tests for SecureFileContext."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures with fresh zone registry."""
        registry = get_zone_registry()
        registry.clear()

        # Register test zones
        registry.register_zone(ZoneConfig(
            name="protected_zone",
            zone_type=ZoneType.IMMUTABLE,
            paths=["/protected"],
            writable_by=["admin"],
            readable_by=["admin", "developer", "viewer"],
        ))
        registry.register_zone(ZoneConfig(
            name="mutable_zone",
            zone_type=ZoneType.MUTABLE,
            paths=["/mutable"],
            writable_by=["admin", "developer"],
            readable_by=["admin", "developer", "viewer"],
        ))

    def test_context_creation(self):
        """Test creating a secure file context."""
        context = SecureFileContext(
            user_id="test_user",
            roles={"developer"},
        )

        assert context.user_id == "test_user"
        assert "developer" in context.roles

    def test_can_read_allowed(self):
        """Test read permission for allowed role."""
        context = SecureFileContext(
            user_id="dev_user",
            roles={"developer"},
        )

        # Developer can read both zones
        assert context.can_read("/protected/file.py") is True
        assert context.can_read("/mutable/file.py") is True

    def test_can_read_denied(self):
        """Test read permission for denied role."""
        context = SecureFileContext(
            user_id="viewer_user",
            roles={"viewer"},
        )

        # Viewer can read both zones
        assert context.can_read("/protected/file.py") is True
        assert context.can_read("/mutable/file.py") is True

    def test_can_write_immutable_denied_for_developer(self):
        """Test write permission denied for developer in immutable zone."""
        context = SecureFileContext(
            user_id="dev_user",
            roles={"developer"},
        )

        # Developer cannot write to immutable zone
        assert context.can_write("/protected/file.py") is False

    def test_can_write_immutable_allowed_for_admin(self):
        """Test write permission allowed for admin in immutable zone."""
        context = SecureFileContext(
            user_id="admin_user",
            roles={"admin"},
        )

        # Admin can write to immutable zone
        assert context.can_write("/protected/file.py") is True

    def test_can_write_mutable_allowed_for_developer(self):
        """Test write permission allowed for developer in mutable zone."""
        context = SecureFileContext(
            user_id="dev_user",
            roles={"developer"},
        )

        # Developer can write to mutable zone
        assert context.can_write("/mutable/file.py") is True

    def test_can_write_mutable_denied_for_viewer(self):
        """Test write permission denied for viewer in mutable zone."""
        context = SecureFileContext(
            user_id="viewer_user",
            roles={"viewer"},
        )

        # Viewer cannot write to any zone
        assert context.can_write("/mutable/file.py") is False
        assert context.can_write("/protected/file.py") is False

    def test_get_zone_info(self):
        """Test getting zone information for a path."""
        context = SecureFileContext(
            user_id="test_user",
            roles={"developer"},
        )

        zone_info = context.get_zone_info("/protected/file.py")
        assert zone_info["matched"] is True
        assert zone_info["zone_name"] == "protected_zone"
        assert zone_info["zone_type"] == ZoneType.IMMUTABLE.value

        zone_info = context.get_zone_info("/mutable/file.py")
        assert zone_info["matched"] is True
        assert zone_info["zone_name"] == "mutable_zone"
        assert zone_info["zone_type"] == ZoneType.MUTABLE.value


class TestSecureFileReadTool:
    """Tests for SecureFileReadTool."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        registry = get_zone_registry()
        registry.clear()

        registry.register_zone(ZoneConfig(
            name="protected",
            zone_type=ZoneType.IMMUTABLE,
            paths=["/protected"],
            writable_by=["admin"],
            readable_by=["admin", "developer"],
        ))

        # Create temp directory and file
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test_read.txt"
        self.test_file.write_text("Line 1\nLine 2\nLine 3\n")

    def teardown_method(self):
        """Clean up temp files."""
        import shutil
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_read_file_success(self):
        """Test successful file read."""
        context = SecureFileContext(user_id="reader", roles={"developer"})
        tool = SecureFileReadTool(context=context)

        result = await tool.execute(path=str(self.test_file))

        assert result.success is True
        assert "Line 1" in result.output
        assert result.metadata["total_lines"] == 3

    @pytest.mark.asyncio
    async def test_read_file_with_line_range(self):
        """Test reading specific line range."""
        context = SecureFileContext(user_id="reader", roles={"developer"})
        tool = SecureFileReadTool(context=context)

        result = await tool.execute(
            path=str(self.test_file),
            start_line=2,
            end_line=3,
        )

        assert result.success is True
        assert "Line 1" not in result.output
        assert "Line 2" in result.output
        assert result.metadata["start_line"] == 2

    @pytest.mark.asyncio
    async def test_read_file_not_found(self):
        """Test reading non-existent file."""
        context = SecureFileContext(user_id="reader", roles={"developer"})
        tool = SecureFileReadTool(context=context)

        result = await tool.execute(path="/nonexistent/file.txt")

        assert result.success is False
        assert "不存在" in result.error

    @pytest.mark.asyncio
    async def test_read_without_context(self):
        """Test reading without security context (anonymous)."""
        tool = SecureFileReadTool(context=None)

        result = await tool.execute(path=str(self.test_file))

        # Should succeed without context
        assert result.success is True


class TestSecureFileWriteTool:
    """Tests for SecureFileWriteTool."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

        registry = get_zone_registry()
        registry.clear()

        # Use temp_dir for zone paths to ensure matching
        protected_path = Path(self.temp_dir) / "protected"
        mutable_path = Path(self.temp_dir) / "mutable"

        registry.register_zone(ZoneConfig(
            name="protected",
            zone_type=ZoneType.IMMUTABLE,
            paths=[str(protected_path)],
            writable_by=["admin"],
        ))
        registry.register_zone(ZoneConfig(
            name="mutable",
            zone_type=ZoneType.MUTABLE,
            paths=[str(mutable_path)],
            writable_by=["admin", "developer"],
        ))

    def teardown_method(self):
        """Clean up temp files."""
        import shutil
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_write_to_mutable_zone_success(self):
        """Test writing to mutable zone as developer."""
        context = SecureFileContext(user_id="dev", roles={"developer"})
        tool = SecureFileWriteTool(context=context)

        test_file = Path(self.temp_dir) / "mutable" / "test.txt"
        result = await tool.execute(
            path=str(test_file),
            content="Test content",
        )

        assert result.success is True
        assert test_file.exists()
        assert test_file.read_text() == "Test content"

    @pytest.mark.asyncio
    async def test_write_to_immutable_zone_denied(self):
        """Test writing to immutable zone as developer is denied."""
        context = SecureFileContext(user_id="dev", roles={"developer"})
        tool = SecureFileWriteTool(context=context)

        test_file = Path(self.temp_dir) / "protected" / "file.py"
        result = await tool.execute(
            path=str(test_file),
            content="malicious code",
        )

        assert result.success is False
        assert "不可变区域" in result.error

    @pytest.mark.asyncio
    async def test_write_to_immutable_zone_as_admin(self):
        """Test writing to immutable zone as admin."""
        context = SecureFileContext(user_id="admin", roles={"admin"})
        tool = SecureFileWriteTool(context=context)

        test_file = Path(self.temp_dir) / "protected" / "admin_test.txt"
        result = await tool.execute(
            path=str(test_file),
            content="admin content",
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_write_append_mode(self):
        """Test append mode."""
        context = SecureFileContext(user_id="dev", roles={"developer"})
        tool = SecureFileWriteTool(context=context)

        test_file = Path(self.temp_dir) / "mutable" / "append_test.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("Initial\n")

        result = await tool.execute(
            path=str(test_file),
            content="Appended\n",
            mode="append",
        )

        assert result.success is True
        assert test_file.read_text() == "Initial\nAppended\n"

    @pytest.mark.asyncio
    async def test_write_create_directories(self):
        """Test automatic directory creation."""
        context = SecureFileContext(user_id="dev", roles={"developer"})
        tool = SecureFileWriteTool(context=context)

        test_file = Path(self.temp_dir) / "mutable" / "deep" / "nested" / "file.txt"
        result = await tool.execute(
            path=str(test_file),
            content="nested content",
            create_dirs=True,
        )

        assert result.success is True
        assert test_file.exists()

    @pytest.mark.asyncio
    async def test_write_missing_required_params(self):
        """Test validation of required parameters."""
        tool = SecureFileWriteTool(context=None)

        result = await tool.execute(path="/some/path")  # missing content

        assert result.success is False
        assert "Missing" in result.error


class TestSecureFileDeleteTool:
    """Tests for SecureFileDeleteTool."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

        registry = get_zone_registry()
        registry.clear()

        # Use temp_dir for zone paths to ensure matching
        protected_path = Path(self.temp_dir) / "protected"
        mutable_path = Path(self.temp_dir) / "mutable"

        registry.register_zone(ZoneConfig(
            name="protected",
            zone_type=ZoneType.IMMUTABLE,
            paths=[str(protected_path)],
            writable_by=["admin"],
        ))
        registry.register_zone(ZoneConfig(
            name="mutable",
            zone_type=ZoneType.MUTABLE,
            paths=[str(mutable_path)],
            writable_by=["admin", "developer"],
        ))

    def teardown_method(self):
        """Clean up temp files."""
        import shutil
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_delete_from_mutable_zone_success(self):
        """Test deleting file from mutable zone."""
        context = SecureFileContext(user_id="dev", roles={"developer"})
        tool = SecureFileDeleteTool(context=context)

        test_file = Path(self.temp_dir) / "mutable" / "delete_me.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("to be deleted")

        result = await tool.execute(
            path=str(test_file),
            confirm=True,
        )

        assert result.success is True
        assert not test_file.exists()

    @pytest.mark.asyncio
    async def test_delete_from_immutable_zone_denied(self):
        """Test deleting from immutable zone is denied."""
        context = SecureFileContext(user_id="dev", roles={"developer"})
        tool = SecureFileDeleteTool(context=context)

        test_file = Path(self.temp_dir) / "protected" / "protected.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("protected content")

        result = await tool.execute(
            path=str(test_file),
            confirm=True,
        )

        assert result.success is False
        assert "不可变区域" in result.error

    @pytest.mark.asyncio
    async def test_delete_requires_confirmation(self):
        """Test delete requires confirmation."""
        context = SecureFileContext(user_id="dev", roles={"developer"})
        tool = SecureFileDeleteTool(context=context)

        result = await tool.execute(
            path="/mutable/file.txt",
            confirm=False,
        )

        assert result.success is False
        assert "确认" in result.error

    @pytest.mark.asyncio
    async def test_delete_nonexistent_file(self):
        """Test deleting non-existent file."""
        context = SecureFileContext(user_id="dev", roles={"developer"})
        tool = SecureFileDeleteTool(context=context)

        result = await tool.execute(
            path="/mutable/nonexistent.txt",
            confirm=True,
        )

        assert result.success is False
        assert "不存在" in result.error


class TestZoneInfoTool:
    """Tests for ZoneInfoTool."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        registry = get_zone_registry()
        registry.clear()

        registry.register_zone(ZoneConfig(
            name="core",
            zone_type=ZoneType.IMMUTABLE,
            paths=["/app/core"],
        ))
        registry.register_zone(ZoneConfig(
            name="extensions",
            zone_type=ZoneType.MUTABLE,
            paths=["/app/extensions"],
        ))

    @pytest.mark.asyncio
    async def test_get_zone_info_for_immutable(self):
        """Test getting zone info for immutable path."""
        tool = ZoneInfoTool()

        result = await tool.execute(path="/app/core/config.py")

        assert result.success is True
        assert result.output["matched"] is True
        assert result.output["zone_name"] == "core"
        assert result.output["is_protected"] is True

    @pytest.mark.asyncio
    async def test_get_zone_info_for_mutable(self):
        """Test getting zone info for mutable path."""
        tool = ZoneInfoTool()

        result = await tool.execute(path="/app/extensions/plugin.py")

        assert result.success is True
        assert result.output["matched"] is True
        assert result.output["zone_name"] == "extensions"
        assert result.output["is_protected"] is False

    @pytest.mark.asyncio
    async def test_get_zone_info_for_unregistered(self):
        """Test getting zone info for unregistered path."""
        tool = ZoneInfoTool()

        result = await tool.execute(path="/unknown/path/file.py")

        assert result.success is True
        assert result.output["matched"] is False
        assert result.output["zone_type"] == ZoneType.MUTABLE.value

    @pytest.mark.asyncio
    async def test_get_zone_info_missing_path(self):
        """Test getting zone info without path parameter."""
        tool = ZoneInfoTool()

        result = await tool.execute()

        assert result.success is False
        assert "路径参数" in result.error


class TestCreateSecureFileTools:
    """Tests for create_secure_file_tools factory function."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        registry = get_zone_registry()
        registry.clear()

        # Register some zones for testing
        registry.register_zone(ZoneConfig(
            name="test_mutable",
            zone_type=ZoneType.MUTABLE,
            paths=["/test"],
            writable_by=["admin", "developer"],
        ))

    def test_factory_creates_all_tools(self):
        """Test factory creates all secure file tools."""
        tools = create_secure_file_tools(
            user_id="test_user",
            roles={"developer"},
        )

        assert "secure_file_read" in tools
        assert "secure_file_write" in tools
        assert "secure_file_delete" in tools
        assert "zone_info" in tools

    def test_factory_tools_have_context(self):
        """Test factory tools have security context attached."""
        tools = create_secure_file_tools(
            user_id="test_user",
            roles={"admin"},
        )

        read_tool = tools["secure_file_read"]
        write_tool = tools["secure_file_write"]
        delete_tool = tools["secure_file_delete"]

        assert read_tool._context is not None
        assert write_tool._context is not None
        assert delete_tool._context is not None

        assert read_tool._context.user_id == "test_user"
        assert "admin" in read_tool._context.roles

    def test_factory_tools_can_set_context(self):
        """Test tools can have context set after creation."""
        tools = create_secure_file_tools(
            user_id="initial_user",
            roles={"viewer"},
        )

        # Create new context
        new_context = SecureFileContext(
            user_id="admin_user",
            roles={"admin"},
        )

        # Set new context
        tools["secure_file_read"].set_context(new_context)

        assert tools["secure_file_read"]._context.user_id == "admin_user"