"""Frontend Agent tools for code generation and validation."""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.agents.llm import BaseLLM, ChatMessage

logger = logging.getLogger(__name__)


@dataclass
class GeneratedFile:
    """A generated file with path and content."""

    path: str
    content: str
    description: str = ""
    language: str = "typescript"


@dataclass
class CodeGenerationResult:
    """Result of code generation."""

    files: List[GeneratedFile]
    dependencies: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of code validation."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


class CodeGenerationTool:
    """Tool for generating React + TypeScript code."""

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def generate_component(
        self,
        description: str,
        component_type: str = "page",
        constraints: Optional[Dict[str, Any]] = None,
    ) -> CodeGenerationResult:
        """Generate a React component based on description.

        Args:
            description: Component description
            component_type: Type of component (page, form, list, card)
            constraints: Additional constraints

        Returns:
            CodeGenerationResult with generated files
        """
        constraints = constraints or {}

        prompt = f"""根据以下描述生成 React + TypeScript 组件代码。

## 组件描述
{description}

## 组件类型
{component_type}

## 技术栈
- React 18 + TypeScript
- Tailwind CSS + shadcn/ui
- Zustand (状态管理)

## 约束条件
{json.dumps(constraints, ensure_ascii=False, indent=2)}

## 要求
1. 使用函数组件和 Hooks
2. 添加完整的 TypeScript 类型定义
3. 使用 Tailwind CSS 进行样式
4. 考虑响应式设计
5. 添加必要的错误处理和加载状态

请输出 JSON 格式：
{{
  "files": [
    {{
      "path": "src/components/ComponentName.tsx",
      "content": "代码内容",
      "description": "文件说明",
      "language": "typescript"
    }}
  ],
  "dependencies": ["需要的 npm 包"]
}}
"""
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await self.llm.chat(messages, temperature=0.3)
            result = self._parse_code_response(response.content)

            return result

        except Exception as e:
            logger.error(f"Code generation error: {e}")
            return CodeGenerationResult(
                files=[],
                errors=[f"代码生成失败: {str(e)}"],
            )

    async def generate_store(
        self,
        name: str,
        state_fields: List[Dict[str, Any]],
        actions: List[str],
    ) -> CodeGenerationResult:
        """Generate a Zustand store.

        Args:
            name: Store name
            state_fields: State field definitions
            actions: Action names

        Returns:
            CodeGenerationResult with generated store file
        """
        prompt = f"""生成一个 Zustand store。

## Store 名称
{name}

## 状态字段
{json.dumps(state_fields, ensure_ascii=False, indent=2)}

## Actions
{json.dumps(actions, ensure_ascii=False, indent=2)}

## 要求
1. 使用 TypeScript 类型定义
2. 包含 devtools 中间件
3. 添加 reset 方法
4. 遵循命名规范

请输出 JSON 格式：
{{
  "files": [
    {{
      "path": "src/stores/use{name}Store.ts",
      "content": "代码内容",
      "description": "Store 文件"
    }}
  ]
}}
"""
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await self.llm.chat(messages, temperature=0.3)
            result = self._parse_code_response(response.content)

            return result

        except Exception as e:
            logger.error(f"Store generation error: {e}")
            return CodeGenerationResult(
                files=[],
                errors=[f"Store 生成失败: {str(e)}"],
            )

    async def generate_api_hook(
        self,
        endpoint: str,
        method: str = "GET",
        data_type: Optional[str] = None,
    ) -> CodeGenerationResult:
        """Generate an API hook for data fetching.

        Args:
            endpoint: API endpoint
            method: HTTP method
            data_type: Response data type name

        Returns:
            CodeGenerationResult with generated hook file
        """
        prompt = f"""生成一个 React Hook 用于 API 调用。

## API 端点
{endpoint}

## HTTP 方法
{method}

## 返回数据类型
{data_type or "unknown"}

## 要求
1. 使用 TypeScript
2. 支持加载状态和错误处理
3. 支持手动刷新
4. 考虑请求取消

请输出 JSON 格式：
{{
  "files": [
    {{
      "path": "src/hooks/use{name}Api.ts",
      "content": "代码内容",
      "description": "API Hook 文件"
    }}
  ],
  "dependencies": []
}}
"""
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await self.llm.chat(messages, temperature=0.3)
            result = self._parse_code_response(response.content)

            return result

        except Exception as e:
            logger.error(f"API hook generation error: {e}")
            return CodeGenerationResult(
                files=[],
                errors=[f"API Hook 生成失败: {str(e)}"],
            )

    def _parse_code_response(self, content: str) -> CodeGenerationResult:
        """Parse LLM response for code generation.

        Args:
            content: LLM response content

        Returns:
            CodeGenerationResult
        """
        # Try to find JSON in response
        json_pattern = r"```json\s*([\s\S]*?)\s*```"
        matches = re.findall(json_pattern, content)

        if matches:
            try:
                data = json.loads(matches[0])
                files = [
                    GeneratedFile(
                        path=f.get("path", "unknown.ts"),
                        content=f.get("content", ""),
                        description=f.get("description", ""),
                        language=f.get("language", "typescript"),
                    )
                    for f in data.get("files", [])
                ]
                return CodeGenerationResult(
                    files=files,
                    dependencies=data.get("dependencies", []),
                )
            except json.JSONDecodeError:
                pass

        # Try direct JSON parse
        try:
            data = json.loads(content)
            files = [
                GeneratedFile(
                    path=f.get("path", "unknown.ts"),
                    content=f.get("content", ""),
                    description=f.get("description", ""),
                    language=f.get("language", "typescript"),
                )
                for f in data.get("files", [])
            ]
            return CodeGenerationResult(
                files=files,
                dependencies=data.get("dependencies", []),
            )
        except json.JSONDecodeError:
            pass

        return CodeGenerationResult(
            files=[],
            errors=["无法解析代码生成结果"],
        )


class CodeValidationTool:
    """Tool for validating generated code."""

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def validate_typescript(self, code: str) -> ValidationResult:
        """Validate TypeScript code for syntax and best practices.

        Args:
            code: TypeScript code to validate

        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []
        suggestions = []

        # Basic syntax checks
        # Check for common issues
        if "any" in code:
            warnings.append("代码中使用了 'any' 类型，建议使用具体类型")

        # Check for proper React hooks usage
        if "useEffect" in code and "return () =>" not in code:
            suggestions.append("useEffect 中可能缺少清理函数")

        # Check for missing imports
        import_pattern = r"import\s+\{([^}]+)\}\s+from\s+['\"]([^'\"]+)['\"]"
        imports = re.findall(import_pattern, code)

        # Check for unused imports
        for imported_items, module in imports:
            items = [item.strip() for item in imported_items.split(",")]
            for item in items:
                # Check if item is used in code (simple check)
                pattern = rf"\b{re.escape(item)}\b"
                # Don't count the import statement itself
                code_without_import = re.sub(import_pattern, "", code, count=1)
                if not re.search(pattern, code_without_import):
                    warnings.append(f"可能未使用的导入: {item} from {module}")

        # Use LLM for deeper analysis
        prompt = f"""检查以下 React/TypeScript 代码的质量问题。

代码：
```typescript
{code}
```

检查以下方面：
1. TypeScript 类型安全
2. React 最佳实践
3. 性能问题
4. 可访问性问题

请输出 JSON 格式：
{{
  "errors": ["严重错误"],
  "warnings": ["警告"],
  "suggestions": ["改进建议"]
}}
"""
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await self.llm.chat(messages, temperature=0.3)
            result = json.loads(response.content)

            errors.extend(result.get("errors", []))
            warnings.extend(result.get("warnings", []))
            suggestions.extend(result.get("suggestions", []))

        except Exception as e:
            logger.warning(f"LLM validation error: {e}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )

    async def check_accessibility(self, code: str) -> ValidationResult:
        """Check accessibility (a11y) issues in the code.

        Args:
            code: React component code

        Returns:
            ValidationResult with a11y issues
        """
        errors = []
        warnings = []
        suggestions = []

        # Check for images without alt
        if "<img" in code and "alt=" not in code:
            errors.append("图片元素缺少 alt 属性")

        # Check for buttons without accessible name
        if "<button" in code:
            button_pattern = r"<button[^>]*>(.*?)</button>"
            buttons = re.findall(button_pattern, code, re.DOTALL)
            for button_content in buttons:
                if not button_content.strip():
                    errors.append("发现空按钮，缺少可访问名称")

        # Check for form inputs without labels
        if "<input" in code or "<textarea" in code:
            if "aria-label" not in code and "<label" not in code:
                warnings.append("表单元素可能缺少关联的标签")

        # Check for click handlers on non-interactive elements
        if "onClick" in code:
            non_interactive_pattern = r"<(div|span|p)[^>]*onClick"
            if re.search(non_interactive_pattern, code):
                warnings.append("非交互元素使用 onClick，建议使用 button 或添加键盘支持")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
        )


class SandboxSubmitTool:
    """Tool for submitting code to sandbox for validation."""

    def __init__(self, sandbox_url: str = "http://localhost:8080"):
        self.sandbox_url = sandbox_url

    async def submit_code(
        self,
        files: List[GeneratedFile],
        task_id: str,
    ) -> Dict[str, Any]:
        """Submit generated code to sandbox for execution.

        Args:
            files: List of generated files
            task_id: Task identifier

        Returns:
            Sandbox execution result
        """
        # This would typically make an HTTP request to the sandbox service
        # For now, return a mock response
        return {
            "success": True,
            "task_id": task_id,
            "output": "代码验证成功",
            "artifacts": {
                "preview_url": f"http://localhost:3000/preview/{task_id}",
            },
        }

    async def check_status(self, task_id: str) -> Dict[str, Any]:
        """Check sandbox execution status.

        Args:
            task_id: Task identifier

        Returns:
            Status information
        """
        # This would check the sandbox service for task status
        return {
            "task_id": task_id,
            "status": "completed",
            "progress": 100,
        }

    async def get_preview_url(self, task_id: str) -> Optional[str]:
        """Get preview URL for the generated code.

        Args:
            task_id: Task identifier

        Returns:
            Preview URL if available
        """
        return f"http://localhost:3000/preview/{task_id}"