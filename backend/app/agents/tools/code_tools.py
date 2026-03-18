"""Code analysis and formatting tools for agents."""

import ast
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from app.agents.tools.base import BaseTool, ToolCategory, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Result of code analysis."""

    issues: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class ComplexityMetrics:
    """Code complexity metrics."""

    cyclomatic_complexity: int = 0
    cognitive_complexity: int = 0
    lines_of_code: int = 0
    maintainability_index: float = 0.0


class CodeAnalysisTool(BaseTool):
    """Tool for analyzing Python code quality and structure."""

    name = "code_analysis"
    description = "分析 Python 代码质量和结构"
    category = ToolCategory.CODE

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="code",
                type="string",
                description="要分析的 Python 代码",
                required=True,
            ),
            ToolParameter(
                name="analysis_type",
                type="string",
                description="分析类型：quality（质量）、complexity（复杂度）、all（全部）",
                required=False,
                default="all",
                enum=["quality", "complexity", "all"],
            ),
        ]

    async def execute(self, **kwargs) -> ToolResult:
        """Analyze Python code.

        Args:
            code: Python code to analyze
            analysis_type: Type of analysis to perform

        Returns:
            ToolResult with analysis results
        """
        error = self.validate_parameters(**kwargs)
        if error:
            return ToolResult(success=False, output=None, error=error)

        code = kwargs.get("code", "")
        analysis_type = kwargs.get("analysis_type", "all")

        try:
            result = AnalysisResult()

            # Parse AST
            try:
                tree = ast.parse(code)
            except SyntaxError as e:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"语法错误: {e.msg} (行 {e.lineno})",
                )

            if analysis_type in ("quality", "all"):
                self._analyze_quality(tree, code, result)

            if analysis_type in ("complexity", "all"):
                self._analyze_complexity(tree, code, result)

            return ToolResult(
                success=True,
                output={
                    "issues": result.issues,
                    "metrics": result.metrics,
                    "suggestions": result.suggestions,
                },
                metadata={
                    "analysis_type": analysis_type,
                    "lines_of_code": len(code.splitlines()),
                },
            )

        except Exception as e:
            logger.error(f"Code analysis error: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=f"代码分析失败: {str(e)}",
            )

    def _analyze_quality(self, tree: ast.AST, code: str, result: AnalysisResult) -> None:
        """Analyze code quality issues."""
        # Check for undefined variables (simple check)
        defined_vars: Set[str] = set()
        used_vars: Set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Add function arguments
                for arg in node.args.args:
                    defined_vars.add(arg.arg)

                # Check function complexity
                if len(node.body) > 50:
                    result.issues.append({
                        "type": "complexity",
                        "message": f"函数 '{node.name}' 过长 ({len(node.body)} 行)",
                        "line": node.lineno,
                        "severity": "warning",
                    })

            elif isinstance(node, ast.ClassDef):
                # Check class docstring
                if not ast.get_docstring(node):
                    result.suggestions.append(
                        f"类 '{node.name}' 缺少文档字符串"
                    )

            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    used_vars.add(node.id)

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("_"):
                        result.issues.append({
                            "type": "style",
                            "message": f"导入私有模块 '{alias.name}'",
                            "line": node.lineno,
                            "severity": "info",
                        })

        # Check for unused imports
        lines = code.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                # Extract module name
                match = re.match(r"(?:from\s+(\S+)\s+)?import\s+(\S+)", stripped)
                if match:
                    module = match.group(2).split(".")[0]
                    if module not in used_vars and module not in defined_vars:
                        # Might be used in type hints or other ways
                        pass  # Skip for now

        # Metrics
        result.metrics["function_count"] = sum(
            1 for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        )
        result.metrics["class_count"] = sum(
            1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        )
        result.metrics["import_count"] = sum(
            1 for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
        )

    def _analyze_complexity(self, tree: ast.AST, code: str, result: AnalysisResult) -> None:
        """Analyze code complexity metrics."""
        metrics = ComplexityMetrics()
        lines = code.splitlines()

        # Count lines of code (excluding empty and comments)
        code_lines = [
            line for line in lines
            if line.strip() and not line.strip().startswith("#")
        ]
        metrics.lines_of_code = len(code_lines)

        # Calculate cyclomatic complexity
        complexity = 1
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
            elif isinstance(node, (ast.And, ast.Or)):
                complexity += 1

        metrics.cyclomatic_complexity = complexity

        # Calculate maintainability index (simplified)
        if metrics.lines_of_code > 0:
            # Simplified maintainability index
            volume = metrics.lines_of_code * complexity
            metrics.maintainability_index = max(0, 171 - 5.2 * (complexity ** 0.5) - 0.23 * volume)

        result.metrics["complexity"] = {
            "cyclomatic": metrics.cyclomatic_complexity,
            "lines_of_code": metrics.lines_of_code,
            "maintainability_index": round(metrics.maintainability_index, 2),
        }

        # Add complexity warnings
        if metrics.cyclomatic_complexity > 10:
            result.issues.append({
                "type": "complexity",
                "message": f"圈复杂度过高 ({metrics.cyclomatic_complexity})，建议拆分函数",
                "severity": "warning",
            })

        if metrics.maintainability_index < 65:
            result.suggestions.append(
                f"可维护性指数较低 ({metrics.maintainability_index:.1f})，考虑重构"
            )


class CodeFormatTool(BaseTool):
    """Tool for formatting Python code."""

    name = "code_format"
    description = "格式化 Python 代码"
    category = ToolCategory.CODE

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="code",
                type="string",
                description="要格式化的 Python 代码",
                required=True,
            ),
            ToolParameter(
                name="formatter",
                type="string",
                description="格式化工具：black、autopep8 或 basic",
                required=False,
                default="basic",
                enum=["black", "autopep8", "basic"],
            ),
            ToolParameter(
                name="line_length",
                type="number",
                description="每行最大字符数",
                required=False,
                default=88,
            ),
        ]

    async def execute(self, **kwargs) -> ToolResult:
        """Format Python code.

        Args:
            code: Python code to format
            formatter: Formatter to use
            line_length: Maximum line length

        Returns:
            ToolResult with formatted code
        """
        error = self.validate_parameters(**kwargs)
        if error:
            return ToolResult(success=False, output=None, error=error)

        code = kwargs.get("code", "")
        formatter = kwargs.get("formatter", "basic")
        line_length = kwargs.get("line_length", 88)

        try:
            if formatter == "black":
                formatted = self._format_black(code, line_length)
            elif formatter == "autopep8":
                formatted = self._format_autopep8(code, line_length)
            else:
                formatted = self._format_basic(code, line_length)

            return ToolResult(
                success=True,
                output=formatted,
                metadata={
                    "formatter": formatter,
                    "original_lines": len(code.splitlines()),
                    "formatted_lines": len(formatted.splitlines()),
                },
            )

        except Exception as e:
            logger.error(f"Code format error: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=f"代码格式化失败: {str(e)}",
            )

    def _format_black(self, code: str, line_length: int) -> str:
        """Format code using black style (simulated)."""
        try:
            import black
            return black.format_str(code, mode=black.Mode(line_length=line_length))
        except ImportError:
            # Fall back to basic formatting if black not installed
            logger.warning("black not installed, using basic formatting")
            return self._format_basic(code, line_length)

    def _format_autopep8(self, code: str, line_length: int) -> str:
        """Format code using autopep8 style."""
        try:
            import autopep8
            return autopep8.fix_code(
                code,
                options={"max_line_length": line_length},
            )
        except ImportError:
            # Fall back to basic formatting
            logger.warning("autopep8 not installed, using basic formatting")
            return self._format_basic(code, line_length)

    def _format_basic(self, code: str, line_length: int) -> str:
        """Basic Python code formatting."""
        lines = code.splitlines()
        formatted_lines = []

        in_docstring = False
        docstring_char = None
        indent_size = 4

        for line in lines:
            # Handle docstrings
            stripped = line.strip()

            if in_docstring:
                if stripped.endswith(docstring_char) and len(stripped) > 3:
                    in_docstring = False
                formatted_lines.append(line)
                continue

            if stripped.startswith('"""') or stripped.startswith("'''"):
                docstring_char = stripped[:3]
                if not stripped.endswith(docstring_char) or len(stripped) == 3:
                    in_docstring = True
                formatted_lines.append(line)
                continue

            # Remove trailing whitespace
            line = line.rstrip()

            # Check line length
            if len(line) > line_length:
                # Try to break long lines
                line = self._break_long_line(line, line_length, indent_size)

            formatted_lines.append(line)

        return "\n".join(formatted_lines)

    def _break_long_line(self, line: str, max_length: int, indent: int) -> str:
        """Attempt to break a long line."""
        if len(line) <= max_length:
            return line

        # Find a good break point
        break_chars = [",", " ", "+", "-", "*", "/", "(", "["]

        for char in break_chars:
            idx = line.rfind(char, 0, max_length)
            if idx > 20:  # Don't break too early
                indent_str = " " * indent
                return line[:idx + 1] + "\n" + indent_str + line[idx + 1:].lstrip()

        return line  # Can't break nicely


class CodeLintTool(BaseTool):
    """Tool for linting Python code."""

    name = "code_lint"
    description = "检查 Python 代码规范"
    category = ToolCategory.CODE

    @property
    def parameters(self) -> List[ToolParameter]:
        return [
            ToolParameter(
                name="code",
                type="string",
                description="要检查的 Python 代码",
                required=True,
            ),
            ToolParameter(
                name="rules",
                type="array",
                description="要检查的规则列表（可选）",
                required=False,
            ),
        ]

    async def execute(self, **kwargs) -> ToolResult:
        """Lint Python code.

        Args:
            code: Python code to lint
            rules: Specific rules to check (optional)

        Returns:
            ToolResult with lint results
        """
        error = self.validate_parameters(**kwargs)
        if error:
            return ToolResult(success=False, output=None, error=error)

        code = kwargs.get("code", "")
        rules = kwargs.get("rules")

        try:
            issues = []

            # Parse AST first
            try:
                tree = ast.parse(code)
            except SyntaxError as e:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"语法错误: {e.msg} (行 {e.lineno})",
                )

            lines = code.splitlines()

            # Run basic lint checks
            self._check_naming(tree, lines, issues)
            self._check_imports(tree, lines, issues)
            self._check_whitespace(lines, issues)
            self._check_docstrings(tree, lines, issues)

            # Filter by rules if specified
            if rules:
                issues = [i for i in issues if i.get("rule") in rules]

            return ToolResult(
                success=True,
                output={
                    "issues": issues,
                    "issue_count": len(issues),
                    "error_count": sum(1 for i in issues if i["severity"] == "error"),
                    "warning_count": sum(1 for i in issues if i["severity"] == "warning"),
                },
                metadata={
                    "lines_checked": len(lines),
                },
            )

        except Exception as e:
            logger.error(f"Code lint error: {e}")
            return ToolResult(
                success=False,
                output=None,
                error=f"代码检查失败: {str(e)}",
            )

    def _check_naming(self, tree: ast.AST, lines: List[str], issues: List[Dict]) -> None:
        """Check naming conventions."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not re.match(r"^[a-z_][a-z0-9_]*$", node.name) and not node.name.startswith("_"):
                    issues.append({
                        "rule": "naming",
                        "message": f"函数名 '{node.name}' 应使用 snake_case 命名",
                        "line": node.lineno,
                        "severity": "warning",
                    })

            elif isinstance(node, ast.ClassDef):
                if not re.match(r"^[A-Z][a-zA-Z0-9]*$", node.name):
                    issues.append({
                        "rule": "naming",
                        "message": f"类名 '{node.name}' 应使用 PascalCase 命名",
                        "line": node.lineno,
                        "severity": "warning",
                    })

            elif isinstance(node, ast.Variable):
                # Check variable names (would need more context)
                pass

    def _check_imports(self, tree: ast.AST, lines: List[str], issues: List[Dict]) -> None:
        """Check import statements."""
        imports_seen = []
        import_lines = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_lines.append((node.lineno, node))

        # Check import order (stdlib, third-party, local)
        # This is a simplified check
        for i, (lineno, node) in enumerate(import_lines):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in imports_seen:
                        issues.append({
                            "rule": "import",
                            "message": f"重复导入 '{alias.name}'",
                            "line": lineno,
                            "severity": "warning",
                        })
                    imports_seen.append(alias.name)

    def _check_whitespace(self, lines: List[str], issues: List[Dict]) -> None:
        """Check whitespace issues."""
        for i, line in enumerate(lines, 1):
            # Trailing whitespace
            if line.rstrip() != line:
                issues.append({
                    "rule": "whitespace",
                    "message": "行末有多余空白字符",
                    "line": i,
                    "severity": "info",
                })

            # Mixed tabs and spaces
            if "\t" in line and "    " in line:
                issues.append({
                    "rule": "whitespace",
                    "message": "混用制表符和空格",
                    "line": i,
                    "severity": "warning",
                })

            # Line too long
            if len(line) > 100:
                issues.append({
                    "rule": "line_length",
                    "message": f"行长度超过 100 字符 ({len(line)})",
                    "line": i,
                    "severity": "info",
                })

    def _check_docstrings(self, tree: ast.AST, lines: List[str], issues: List[Dict]) -> None:
        """Check for missing docstrings."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                docstring = ast.get_docstring(node)
                if not docstring:
                    node_type = "函数" if isinstance(node, ast.FunctionDef) else "类"
                    if isinstance(node, ast.Module):
                        continue  # Skip module-level check for now

                    issues.append({
                        "rule": "docstring",
                        "message": f"{node_type} '{node.name}' 缺少文档字符串",
                        "line": node.lineno,
                        "severity": "info",
                    })