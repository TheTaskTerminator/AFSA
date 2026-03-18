"""File operation tools for agents."""

import logging
from pathlib import Path
from typing import List, Optional

from app.agents.tools.base import BaseTool, ToolCategory, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


class FileReadTool(BaseTool):
    """Tool for reading files from the filesystem."""

    name = "file_read"
    description = "读取文件内容"
    category = ToolCategory.FILE

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

    async def execute(self, **kwargs) -> ToolResult:
        """Read file content.

        Args:
            path: File path
            start_line: Start line number (1-indexed)
            end_line: End line number (inclusive)

        Returns:
            ToolResult with file content
        """
        error = self.validate_parameters(**kwargs)
        if error:
            return ToolResult(success=False, output=None, error=error)

        path = kwargs.get("path")
        start_line = kwargs.get("start_line", 1)
        end_line = kwargs.get("end_line")

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
            logger.error(f"File read error: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=f"读取文件失败: {str(e)}",
            )


class FileWriteTool(BaseTool):
    """Tool for writing files to the filesystem."""

    name = "file_write"
    description = "写入文件内容"
    category = ToolCategory.FILE

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

    async def execute(self, **kwargs) -> ToolResult:
        """Write content to file.

        Args:
            path: File path
            content: Content to write
            mode: Write mode (write or append)
            create_dirs: Create parent directories if needed

        Returns:
            ToolResult indicating success or failure
        """
        error = self.validate_parameters(**kwargs)
        if error:
            return ToolResult(success=False, output=None, error=error)

        path = kwargs.get("path")
        content = kwargs.get("content", "")
        mode = kwargs.get("mode", "write")
        create_dirs = kwargs.get("create_dirs", True)

        try:
            file_path = Path(path)

            # Create parent directories if needed
            if create_dirs and not file_path.parent.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            write_mode = "a" if mode == "append" else "w"
            with open(file_path, write_mode, encoding="utf-8") as f:
                f.write(content)

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
            logger.error(f"File write error: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=f"写入文件失败: {str(e)}",
            )


class FileListTool(BaseTool):
    """Tool for listing directory contents."""

    name = "file_list"
    description = "列出目录内容"
    category = ToolCategory.FILE

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="path",
                type="string",
                description="目录路径",
                required=False,
                default=".",
            ),
            ToolParameter(
                name="pattern",
                type="string",
                description="文件匹配模式（如 *.py）",
                required=False,
            ),
            ToolParameter(
                name="recursive",
                type="boolean",
                description="是否递归列出子目录",
                required=False,
                default=False,
            ),
        ]

    async def execute(self, **kwargs) -> ToolResult:
        """List directory contents.

        Args:
            path: Directory path
            pattern: File pattern to match
            recursive: List recursively

        Returns:
            ToolResult with file list
        """
        path = kwargs.get("path", ".")
        pattern = kwargs.get("pattern", "*")
        recursive = kwargs.get("recursive", False)

        try:
            dir_path = Path(path)

            if not dir_path.exists():
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"目录不存在: {path}",
                )

            if not dir_path.is_dir():
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"路径不是目录: {path}",
                )

            # List files
            if recursive:
                files = list(dir_path.rglob(pattern))
            else:
                files = list(dir_path.glob(pattern))

            # Format output
            result = []
            for f in sorted(files):
                result.append({
                    "name": f.name,
                    "path": str(f.relative_to(dir_path)),
                    "type": "directory" if f.is_dir() else "file",
                    "size": f.stat().st_size if f.is_file() else None,
                })

            return ToolResult(
                success=True,
                output=result,
                metadata={
                    "path": str(dir_path),
                    "pattern": pattern,
                    "count": len(result),
                },
            )

        except PermissionError:
            return ToolResult(
                success=False,
                output=None,
                error=f"没有权限访问目录: {path}",
            )
        except Exception as e:
            logger.error(f"File list error: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=f"列出目录失败: {str(e)}",
            )


class FileDeleteTool(BaseTool):
    """Tool for deleting files."""

    name = "file_delete"
    description = "删除文件"
    category = ToolCategory.FILE

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

    async def execute(self, **kwargs) -> ToolResult:
        """Delete a file.

        Args:
            path: File path to delete
            confirm: Confirmation flag

        Returns:
            ToolResult indicating success or failure
        """
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
            logger.error(f"File delete error: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=f"删除文件失败: {str(e)}",
            )