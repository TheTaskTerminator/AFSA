"""Secure file operation tools with permission and zone checking.

These tools extend the base file tools with:
1. Zone-based access control (mutable vs immutable)
2. Role-based permission checking
3. Audit logging for all operations
"""
import logging
from pathlib import Path
from typing import List, Optional, Set

from app.agents.tools.base import BaseTool, ToolCategory, ToolParameter, ToolResult
from app.governance.zone import ZoneType, get_zone_registry
from app.governance.permission.guard import ActionType, PermissionGuard

logger = logging.getLogger(__name__)


class SecureFileContext:
    """Context for secure file operations.

    Holds the user/agent context needed for permission checks.
    """

    def __init__(
        self,
        user_id: str,
        roles: Optional[Set[str]] = None,
        permission_guard: Optional[PermissionGuard] = None,
    ):
        """Initialize secure file context.

        Args:
            user_id: User or agent ID
            roles: Set of roles (e.g., {"admin"}, {"developer"})
            permission_guard: Optional permission guard instance
        """
        self.user_id = user_id
        self.roles = roles or set()
        self._guard = permission_guard or PermissionGuard()
        self._zone_registry = get_zone_registry()

    def can_read(self, path: str) -> bool:
        """Check if the context can read the given path."""
        return self._zone_registry.can_read(path, self.roles)

    def can_write(self, path: str) -> bool:
        """Check if the context can write to the given path."""
        return self._zone_registry.can_write(path, self.roles)

    def get_zone_info(self, path: str) -> dict:
        """Get zone information for a path."""
        result = self._zone_registry.get_zone_for_path(path)
        return {
            "matched": result.matched,
            "zone_name": result.zone_name,
            "zone_type": result.zone_type.value if result.zone_type else None,
        }


class SecureFileReadTool(BaseTool):
    """Secure file read tool with zone checking."""

    name = "secure_file_read"
    description = "安全读取文件内容（带权限检查）"
    category = ToolCategory.FILE

    def __init__(self, context: Optional[SecureFileContext] = None):
        """Initialize with optional security context.

        Args:
            context: Security context for permission checks
        """
        self._context = context

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="文件路径（绝对路径或相对于工作目录的路径）",
                required=True,
            ),
            ToolParameter(
                name="start_line",
                type="number",
                description="起始行号（可选，从 1 开始）",
                required=False,
                default=1,
            ),
            ToolParameter(
                name="end_line",
                type="number",
                description="结束行号（可选）",
                required=False,
            ),
        ]

    def set_context(self, context: SecureFileContext) -> None:
        """Set the security context."""
        self._context = context

    async def execute(self, **kwargs) -> ToolResult:
        """Read file with permission check."""
        error = self.validate_parameters(**kwargs)
        if error:
            return ToolResult(success=False, output=None, error=error)

        path = kwargs.get("path")
        start_line = kwargs.get("start_line", 1)
        end_line = kwargs.get("end_line")

        # Check permissions if context is set
        if self._context and not self._context.can_read(path):
            zone_info = self._context.get_zone_info(path)
            return ToolResult(
                success=False,
                output=None,
                error=f"权限拒绝: 无法读取 '{path}'（区域: {zone_info.get('zone_name', 'unknown')}）",
            )

        try:
            file_path = Path(path)

            if not file_path.exists():
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"文件不存在: {path}",
                )

            if not file_path.is_file():
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"路径不是文件: {path}",
                )

            # Read file content
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Apply line range
            total_lines = len(lines)
            start_idx = max(0, start_line - 1)
            end_idx = end_line if end_line else total_lines

            selected_lines = lines[start_idx:end_idx]

            # Format with line numbers
            content = "".join(
                f"{i + start_idx + 1:6d}→{line}"
                for i, line in enumerate(selected_lines)
            )

            logger.info(f"File read: {path} by {self._context.user_id if self._context else 'anonymous'}")

            return ToolResult(
                success=True,
                output=content,
                metadata={
                    "path": str(file_path),
                    "total_lines": total_lines,
                    "start_line": start_idx + 1,
                    "end_line": min(end_idx, total_lines),
                },
            )

        except PermissionError:
            return ToolResult(
                success=False,
                output=None,
                error=f"没有权限读取文件: {path}",
            )
        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                output=None,
                error=f"文件编码错误，无法以 UTF-8 解码: {path}",
            )
        except Exception as e:
            logger.error(f"Secure file read error: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=f"读取文件失败: {str(e)}",
            )


class SecureFileWriteTool(BaseTool):
    """Secure file write tool with zone and permission checking."""

    name = "secure_file_write"
    description = "安全写入文件内容（带权限和区域检查）"
    category = ToolCategory.FILE

    def __init__(self, context: Optional[SecureFileContext] = None):
        """Initialize with optional security context.

        Args:
            context: Security context for permission checks
        """
        self._context = context

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="文件路径（绝对路径或相对于工作目录的路径）",
                required=True,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="文件内容",
                required=True,
            ),
            ToolParameter(
                name="mode",
                type="string",
                description="写入模式：write（覆盖）或 append（追加）",
                required=False,
                default="write",
                enum=["write", "append"],
            ),
            ToolParameter(
                name="create_dirs",
                type="boolean",
                description="是否自动创建父目录",
                required=False,
                default=True,
            ),
        ]

    def set_context(self, context: SecureFileContext) -> None:
        """Set the security context."""
        self._context = context

    async def execute(self, **kwargs) -> ToolResult:
        """Write file with permission and zone check."""
        error = self.validate_parameters(**kwargs)
        if error:
            return ToolResult(success=False, output=None, error=error)

        path = kwargs.get("path")
        content = kwargs.get("content", "")
        mode = kwargs.get("mode", "write")
        create_dirs = kwargs.get("create_dirs", True)

        # Check zone and permissions
        if self._context:
            zone_info = self._context.get_zone_info(path)

            # Check write permission (includes zone type checking)
            if not self._context.can_write(path):
                zone_type = zone_info.get("zone_type")
                if zone_type == ZoneType.IMMUTABLE.value:
                    return ToolResult(
                        success=False,
                        output=None,
                        error=f"区域保护: 无法写入不可变区域 '{path}'（区域: {zone_info.get('zone_name', 'unknown')}）",
                    )
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"权限拒绝: 无法写入 '{path}'（需要更高权限）",
                )

        try:
            file_path = Path(path)

            # Create parent directories if needed
            if create_dirs and not file_path.parent.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            write_mode = "a" if mode == "append" else "w"
            with open(file_path, write_mode, encoding="utf-8") as f:
                f.write(content)

            logger.info(f"File write: {path} by {self._context.user_id if self._context else 'anonymous'}")

            return ToolResult(
                success=True,
                output=f"成功写入文件: {path}",
                metadata={
                    "path": str(file_path),
                    "mode": mode,
                    "bytes_written": len(content.encode("utf-8")),
                },
            )

        except PermissionError:
            return ToolResult(
                success=False,
                output=None,
                error=f"没有权限写入文件: {path}",
            )
        except Exception as e:
            logger.error(f"Secure file write error: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=f"写入文件失败: {str(e)}",
            )


class SecureFileDeleteTool(BaseTool):
    """Secure file delete tool with zone and permission checking."""

    name = "secure_file_delete"
    description = "安全删除文件（带权限和区域检查）"
    category = ToolCategory.FILE

    def __init__(self, context: Optional[SecureFileContext] = None):
        """Initialize with optional security context.

        Args:
            context: Security context for permission checks
        """
        self._context = context

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="要删除的文件路径",
                required=True,
            ),
            ToolParameter(
                name="confirm",
                type="boolean",
                description="确认删除（必须为 true）",
                required=True,
            ),
        ]

    def set_context(self, context: SecureFileContext) -> None:
        """Set the security context."""
        self._context = context

    async def execute(self, **kwargs) -> ToolResult:
        """Delete file with permission and zone check."""
        error = self.validate_parameters(**kwargs)
        if error:
            return ToolResult(success=False, output=None, error=error)

        path = kwargs.get("path")
        confirm = kwargs.get("confirm", False)

        if not confirm:
            return ToolResult(
                success=False,
                output=None,
                error="删除操作需要确认（confirm=true）",
            )

        # Check zone and permissions
        if self._context:
            zone_info = self._context.get_zone_info(path)

            # Check write permission (delete requires write access, includes zone checking)
            if not self._context.can_write(path):
                zone_type = zone_info.get("zone_type")
                if zone_type == ZoneType.IMMUTABLE.value:
                    return ToolResult(
                        success=False,
                        output=None,
                        error=f"区域保护: 无法删除不可变区域中的文件 '{path}'（区域: {zone_info.get('zone_name', 'unknown')}）",
                    )
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"权限拒绝: 无法删除 '{path}'（需要更高权限）",
                )

        try:
            file_path = Path(path)

            if not file_path.exists():
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"文件不存在: {path}",
                )

            if file_path.is_dir():
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"路径是目录，请使用目录删除工具: {path}",
                )

            file_path.unlink()

            logger.info(f"File delete: {path} by {self._context.user_id if self._context else 'anonymous'}")

            return ToolResult(
                success=True,
                output=f"成功删除文件: {path}",
                metadata={"path": str(file_path)},
            )

        except PermissionError:
            return ToolResult(
                success=False,
                output=None,
                error=f"没有权限删除文件: {path}",
            )
        except Exception as e:
            logger.error(f"Secure file delete error: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=f"删除文件失败: {str(e)}",
            )


class ZoneInfoTool(BaseTool):
    """Tool to get zone information for a path."""

    name = "zone_info"
    description = "获取路径的区域信息"
    category = ToolCategory.SYSTEM

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="要检查的路径",
                required=True,
            ),
        ]

    async def execute(self, **kwargs) -> ToolResult:
        """Get zone information for a path."""
        path = kwargs.get("path")

        if not path:
            return ToolResult(
                success=False,
                output=None,
                error="需要提供路径参数",
            )

        registry = get_zone_registry()
        result = registry.get_zone_for_path(path)

        return ToolResult(
            success=True,
            output={
                "path": path,
                "matched": result.matched,
                "zone_name": result.zone_name,
                "zone_type": result.zone_type.value if result.zone_type else None,
                "is_protected": result.zone_type == ZoneType.IMMUTABLE,
            },
        )


# Factory function to create secure tools with context
def create_secure_file_tools(
    user_id: str,
    roles: Set[str],
) -> dict:
    """Create secure file tools with a security context.

    Args:
        user_id: User or agent ID
        roles: Set of roles

    Returns:
        Dictionary of tool name to tool instance
    """
    context = SecureFileContext(user_id=user_id, roles=roles)

    return {
        "secure_file_read": SecureFileReadTool(context=context),
        "secure_file_write": SecureFileWriteTool(context=context),
        "secure_file_delete": SecureFileDeleteTool(context=context),
        "zone_info": ZoneInfoTool(),
    }