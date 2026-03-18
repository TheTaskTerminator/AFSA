"""Backend Agent tools for API and database code generation."""

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
    language: str = "python"


@dataclass
class APIGenerationResult:
    """Result of API code generation."""

    files: List[GeneratedFile] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    migrations: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class ModelDefinition:
    """Database model definition."""

    name: str
    table_name: str
    fields: List[Dict[str, Any]]
    relationships: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class APISpec:
    """API specification."""

    path: str
    method: str
    description: str
    request_schema: Optional[str] = None
    response_schema: Optional[str] = None
    auth_required: bool = True


class APIGenerationTool:
    """Tool for generating FastAPI code."""

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def generate_crud_api(
        self,
        model_name: str,
        fields: List[Dict[str, Any]],
        constraints: Optional[Dict[str, Any]] = None,
    ) -> APIGenerationResult:
        """Generate CRUD API for a model.

        Args:
            model_name: Model name in PascalCase
            fields: Field definitions
            constraints: Additional constraints

        Returns:
            APIGenerationResult with generated files
        """
        constraints = constraints or {}

        prompt = f"""生成完整的 CRUD API 代码。

## 模型名称
{model_name}

## 字段定义
{json.dumps(fields, ensure_ascii=False, indent=2)}

## 约束条件
{json.dumps(constraints, ensure_ascii=False, indent=2)}

## 要求
1. 生成以下文件：
   - app/api/v1/{model_name.lower()}.py (API 路由)
   - app/models/{model_name.lower()}.py (SQLAlchemy 模型)
   - app/schemas/{model_name.lower()}.py (Pydantic Schemas)
   - app/repositories/{model_name.lower()}.py (Repository)

2. 使用异步代码
3. 添加类型注解
4. 实现完整的 CRUD 操作
5. 添加错误处理

请输出 JSON 格式：
{{
  "files": [
    {{
      "path": "文件路径",
      "content": "代码内容",
      "description": "文件说明",
      "language": "python"
    }}
  ],
  "dependencies": ["需要的包"],
  "migrations": ["迁移 SQL"]
}}
"""
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await self.llm.chat(messages, temperature=0.3)
            result = self._parse_generation_response(response.content)
            return result

        except Exception as e:
            logger.error(f"API generation error: {e}")
            return APIGenerationResult(
                errors=[f"API 生成失败: {str(e)}"],
            )

    async def generate_endpoint(
        self,
        path: str,
        method: str,
        description: str,
        request_schema: Optional[Dict[str, Any]] = None,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> APIGenerationResult:
        """Generate a single API endpoint.

        Args:
            path: API path
            method: HTTP method
            description: Endpoint description
            request_schema: Request body schema
            response_schema: Response body schema

        Returns:
            APIGenerationResult with generated endpoint
        """
        prompt = f"""生成单个 API 端点代码。

## API 路径
{path}

## HTTP 方法
{method}

## 描述
{description}

## 请求 Schema
{json.dumps(request_schema, ensure_ascii=False, indent=2) if request_schema else '无'}

## 响应 Schema
{json.dumps(response_schema, ensure_ascii=False, indent=2) if response_schema else '无'}

## 要求
1. 使用 FastAPI 路由装饰器
2. 添加完整的类型注解
3. 实现错误处理
4. 添加 API 文档

请输出 JSON 格式：
{{
  "files": [
    {{
      "path": "app/api/v1/endpoint.py",
      "content": "代码内容",
      "description": "API 端点"
    }}
  ]
}}
"""
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await self.llm.chat(messages, temperature=0.3)
            result = self._parse_generation_response(response.content)
            return result

        except Exception as e:
            logger.error(f"Endpoint generation error: {e}")
            return APIGenerationResult(
                errors=[f"端点生成失败: {str(e)}"],
            )

    async def generate_model(
        self,
        model_name: str,
        fields: List[Dict[str, Any]],
        relationships: Optional[List[Dict[str, str]]] = None,
    ) -> APIGenerationResult:
        """Generate SQLAlchemy model.

        Args:
            model_name: Model name
            fields: Field definitions
            relationships: Relationship definitions

        Returns:
            APIGenerationResult with generated model
        """
        prompt = f"""生成 SQLAlchemy 数据模型。

## 模型名称
{model_name}

## 字段定义
{json.dumps(fields, ensure_ascii=False, indent=2)}

## 关联关系
{json.dumps(relationships, ensure_ascii=False, indent=2) if relationships else '无'}

## 要求
1. 使用 SQLAlchemy 2.0 语法
2. 添加类型注解
3. 实现 __repr__ 方法
4. 添加时间戳字段

请输出 JSON 格式：
{{
  "files": [
    {{
      "path": "app/models/{model_name.lower()}.py",
      "content": "代码内容",
      "description": "数据模型"
    }}
  ],
  "migrations": ["迁移 SQL"]
}}
"""
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await self.llm.chat(messages, temperature=0.3)
            result = self._parse_generation_response(response.content)
            return result

        except Exception as e:
            logger.error(f"Model generation error: {e}")
            return APIGenerationResult(
                errors=[f"模型生成失败: {str(e)}"],
            )

    def _parse_generation_response(self, content: str) -> APIGenerationResult:
        """Parse LLM response for code generation."""
        # Try to find JSON in response
        json_pattern = r"```json\s*([\s\S]*?)\s*```"
        matches = re.findall(json_pattern, content)

        if matches:
            try:
                data = json.loads(matches[0])
                files = [
                    GeneratedFile(
                        path=f.get("path", "unknown.py"),
                        content=f.get("content", ""),
                        description=f.get("description", ""),
                        language=f.get("language", "python"),
                    )
                    for f in data.get("files", [])
                ]
                return APIGenerationResult(
                    files=files,
                    dependencies=data.get("dependencies", []),
                    migrations=data.get("migrations", []),
                )
            except json.JSONDecodeError:
                pass

        # Try direct JSON parse
        try:
            data = json.loads(content)
            files = [
                GeneratedFile(
                    path=f.get("path", "unknown.py"),
                    content=f.get("content", ""),
                    description=f.get("description", ""),
                    language=f.get("language", "python"),
                )
                for f in data.get("files", [])
            ]
            return APIGenerationResult(
                files=files,
                dependencies=data.get("dependencies", []),
                migrations=data.get("migrations", []),
            )
        except json.JSONDecodeError:
            pass

        return APIGenerationResult(
            errors=["无法解析代码生成结果"],
        )


class SchemaGenerationTool:
    """Tool for generating Pydantic schemas."""

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def generate_schema(
        self,
        name: str,
        fields: List[Dict[str, Any]],
        include_crud_variants: bool = True,
    ) -> APIGenerationResult:
        """Generate Pydantic schemas.

        Args:
            name: Schema name
            fields: Field definitions
            include_crud_variants: Include Create/Update/Response variants

        Returns:
            APIGenerationResult with generated schemas
        """
        prompt = f"""生成 Pydantic v2 Schemas。

## Schema 名称
{name}

## 字段定义
{json.dumps(fields, ensure_ascii=False, indent=2)}

## 要求
1. 使用 Pydantic v2 语法
2. {"生成 Base/Create/Update/Response 变体" if include_crud_variants else "生成基础 Schema"}
3. 添加 Field 描述
4. 使用 ConfigDict 配置

请输出 JSON 格式：
{{
  "files": [
    {{
      "path": "app/schemas/{name.lower()}.py",
      "content": "代码内容",
      "description": "Pydantic Schemas"
    }}
  ]
}}
"""
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await self.llm.chat(messages, temperature=0.3)
            result = self._parse_generation_response(response.content)
            return result

        except Exception as e:
            logger.error(f"Schema generation error: {e}")
            return APIGenerationResult(
                errors=[f"Schema 生成失败: {str(e)}"],
            )

    def _parse_generation_response(self, content: str) -> APIGenerationResult:
        """Parse LLM response."""
        json_pattern = r"```json\s*([\s\S]*?)\s*```"
        matches = re.findall(json_pattern, content)

        if matches:
            try:
                data = json.loads(matches[0])
                files = [
                    GeneratedFile(
                        path=f.get("path", "unknown.py"),
                        content=f.get("content", ""),
                        description=f.get("description", ""),
                        language="python",
                    )
                    for f in data.get("files", [])
                ]
                return APIGenerationResult(files=files)
            except json.JSONDecodeError:
                pass

        try:
            data = json.loads(content)
            files = [
                GeneratedFile(
                    path=f.get("path", "unknown.py"),
                    content=f.get("content", ""),
                    description=f.get("description", ""),
                    language="python",
                )
                for f in data.get("files", [])
            ]
            return APIGenerationResult(files=files)
        except json.JSONDecodeError:
            pass

        return APIGenerationResult(errors=["无法解析生成结果"])


class CodeReviewTool:
    """Tool for reviewing generated backend code."""

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def review_code(self, code: str, file_type: str = "api") -> Dict[str, Any]:
        """Review generated code for issues.

        Args:
            code: Code to review
            file_type: Type of file (api, model, schema)

        Returns:
            Review result with issues and suggestions
        """
        prompt = f"""审查以下 Python 代码。

## 代码类型
{file_type}

## 代码
```python
{code}
```

## 检查项目
1. 安全问题 (SQL 注入、XSS 等)
2. 性能问题
3. 代码风格
4. 最佳实践
5. 错误处理

请输出 JSON 格式：
{{
  "issues": [
    {{
      "severity": "error|warning|info",
      "line": 10,
      "message": "问题描述",
      "suggestion": "改进建议"
    }}
  ],
  "overall_score": 0-100,
  "summary": "总体评价"
}}
"""
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await self.llm.chat(messages, temperature=0.3)
            result = json.loads(response.content)
            return result
        except Exception as e:
            logger.warning(f"Code review error: {e}")
            return {
                "issues": [],
                "overall_score": 0,
                "summary": f"代码审查失败: {str(e)}",
            }

    async def check_security(self, code: str) -> Dict[str, Any]:
        """Check for security issues.

        Args:
            code: Code to check

        Returns:
            Security check result
        """
        issues = []

        # Check for SQL injection patterns
        if "f\"" in code and "execute" in code:
            issues.append({
                "severity": "error",
                "type": "sql_injection",
                "message": "可能的 SQL 注入风险：字符串格式化用于 SQL 查询",
            })

        # Check for hardcoded credentials
        if re.search(r"password\s*=\s*[\"']", code, re.IGNORECASE):
            issues.append({
                "severity": "warning",
                "type": "hardcoded_credentials",
                "message": "发现硬编码的密码",
            })

        # Check for missing authentication
        if "@router" in code and "get_current_user" not in code:
            issues.append({
                "severity": "info",
                "type": "missing_auth",
                "message": "API 端点可能缺少认证检查",
            })

        return {
            "has_issues": len([i for i in issues if i["severity"] == "error"]) > 0,
            "issues": issues,
        }