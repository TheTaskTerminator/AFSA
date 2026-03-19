"""Backend Agent prompt templates.

This module contains prompt templates for the Backend Agent,
including system prompts, API generation templates, and database patterns.
"""

# System prompt for Backend Agent
BACKEND_SYSTEM_PROMPT = """你是一位专业的后端开发 Agent，负责根据需求生成高质量的 Python + FastAPI 代码。

## 你的职责

1. **API 开发**: 设计和实现 RESTful API 端点
2. **数据库操作**: 实现数据模型和 CRUD 操作
3. **业务逻辑**: 实现核心业务逻辑
4. **安全控制**: 实现认证、授权和数据验证

## 技术栈

- **框架**: FastAPI
- **ORM**: SQLAlchemy 2.0 (async)
- **数据库**: PostgreSQL
- **缓存**: Redis
- **验证**: Pydantic v2
- **消息队列**: NATS

## 代码规范

1. 使用异步代码 (async/await)
2. 所有 API 都要有完整的类型注解
3. 使用 Pydantic 进行数据验证
4. 遵循 RESTful API 设计原则
5. 添加适当的错误处理和日志记录

## 输出格式

当生成代码时，使用 JSON 格式输出：

```json
{
  "type": "code_generation",
  "files": [
    {
      "path": "app/api/v1/users.py",
      "content": "# 代码内容",
      "description": "文件说明"
    }
  ],
  "dependencies": ["需要的包"],
  "migrations": ["迁移脚本"]
}
```

当需要澄清时：
```json
{
  "type": "clarification",
  "questions": [
    {
      "id": "q1",
      "question": "问题描述",
      "options": ["选项A", "选项B"]
    }
  ]
}
```

## 注意事项

- 使用依赖注入模式
- 实现适当的权限检查
- 考虑并发和性能
- 添加 API 文档 (OpenAPI)
"""

# API endpoint template
API_ENDPOINT_TEMPLATE = """from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.db.session import get_db
from app.schemas.{model_lower} import {model}Create, {model}Update, {model}Response
from app.api.deps import get_current_user

router = APIRouter(prefix=\"/{model_lower}s\", tags=[\"{model}\"])


@router.get(\"/\", response_model=List[{model}Response])
async def list_{model_lower}s(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    \"\"\"获取{model_cn}列表。\"\"\"
    # TODO: 实现列表查询
    return []


@router.get(\"/{{id}}\", response_model={model}Response)
async def get_{model_lower}(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    \"\"\"获取单个{model_cn}。\"\"\"
    # TODO: 实现单个查询
    raise HTTPException(status_code=404, detail=\"{model_cn}不存在\")


@router.post(\"/\", response_model={model}Response, status_code=status.HTTP_201_CREATED)
async def create_{model_lower}(
    data: {model}Create,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    \"\"\"创建{model_cn}。\"\"\"
    # TODO: 实现创建逻辑
    return {{}}


@router.put(\"/{{id}}\", response_model={model}Response)
async def update_{model_lower}(
    id: int,
    data: {model}Update,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    \"\"\"更新{model_cn}。\"\"\"
    # TODO: 实现更新逻辑
    raise HTTPException(status_code=404, detail=\"{model_cn}不存在\")


@router.delete(\"/{{id}}\", status_code=status.HTTP_204_NO_CONTENT)
async def delete_{model_lower}(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user),
):
    \"\"\"删除{model_cn}。\"\"\"
    # TODO: 实现删除逻辑
    return None
"""

# SQLAlchemy model template
MODEL_TEMPLATE = """from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class {model}(Base):
    \"\"\"{model_cn}模型。\"\"\"

    __tablename__ = \"{table_name}\"

    id = Column(Integer, primary_key=True, index=True)
    {fields}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f\"<{model}(id={{self.id}})>\"
"""

# Pydantic schema template
SCHEMA_TEMPLATE = """from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional, List


class {model}Base(BaseModel):
    \"\"\"{model_cn}基础模型。\"\"\"
    {base_fields}


class {model}Create({model}Base):
    \"\"\"{model_cn}创建模型。\"\"\"
    pass


class {model}Update(BaseModel):
    \"\"\"{model_cn}更新模型。\"\"\"
    {update_fields}


class {model}Response({model}Base):
    \"\"\"{model_cn}响应模型。\"\"\"
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
"""

# Repository template
REPOSITORY_TEMPLATE = """from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.{model_lower} import {Model}
from app.schemas.{model_lower} import {Model}Create, {Model}Update


class {Model}Repository:
    \"\"\"{model_cn}仓储。\"\"\"

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: {Model}Create) -> {Model}:
        \"\"\"创建{model_cn}。\"\"\"
        obj = {Model}(**data.model_dump())
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def get_by_id(self, id: int) -> Optional[{Model}]:
        \"\"\"根据 ID 获取{model_cn}。\"\"\"
        result = await self.db.execute(
            select({Model}).where({Model}.id == id)
        )
        return result.scalar_one_or_none()

    async def get_list(self, skip: int = 0, limit: int = 100) -> List[{Model}]:
        \"\"\"获取{model_cn}列表。\"\"\"
        result = await self.db.execute(
            select({Model}).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def update(self, id: int, data: {Model}Update) -> Optional[{Model}]:
        \"\"\"更新{model_cn}。\"\"\"
        obj = await self.get_by_id(id)
        if not obj:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, id: int) -> bool:
        \"\"\"删除{model_cn}。\"\"\"
        obj = await self.get_by_id(id)
        if not obj:
            return False
        await self.db.delete(obj)
        await self.db.commit()
        return True
"""


def get_system_prompt() -> str:
    """Get the system prompt for Backend Agent."""
    return BACKEND_SYSTEM_PROMPT


def get_api_template(model: str, model_cn: str = "") -> str:
    """Get API endpoint template.

    Args:
        model: Model name in PascalCase
        model_cn: Model name in Chinese for documentation

    Returns:
        Template string
    """
    model_lower = model.lower()
    model_cn = model_cn or model
    return API_ENDPOINT_TEMPLATE.format(
        model=model,
        model_lower=model_lower,
        model_cn=model_cn,
    )


def get_model_template(model: str, fields: str, model_cn: str = "") -> str:
    """Get SQLAlchemy model template.

    Args:
        model: Model name in PascalCase
        fields: Field definitions
        model_cn: Model name in Chinese

    Returns:
        Template string
    """
    table_name = f"{model.lower()}s"
    model_cn = model_cn or model
    return MODEL_TEMPLATE.format(
        model=model,
        table_name=table_name,
        fields=fields,
        model_cn=model_cn,
    )


def get_schema_template(model: str, base_fields: str = "", update_fields: str = "") -> str:
    """Get Pydantic schema template.

    Args:
        model: Model name in PascalCase
        base_fields: Base model fields
        update_fields: Update model fields

    Returns:
        Template string
    """
    return SCHEMA_TEMPLATE.format(
        model=model,
        base_fields=base_fields or "pass",
        update_fields=update_fields or "pass",
    )


def detect_api_type(description: str) -> str:
    """Detect API type from description.

    Args:
        description: API description

    Returns:
        Detected API type
    """
    keywords_map = {
        "crud": ["CRUD", "增删改查", "管理", "列表", "详情"],
        "auth": ["登录", "认证", "授权", "auth", "login", "token"],
        "search": ["搜索", "查询", "过滤", "search", "filter"],
        "webhook": ["webhook", "回调", "callback"],
        "websocket": ["websocket", "实时", "推送", "realtime"],
    }

    description_lower = description.lower()
    for api_type, keywords in keywords_map.items():
        for keyword in keywords:
            if keyword.lower() in description_lower:
                return api_type

    return "crud"  # Default


def extract_model_name(description: str) -> str:
    """Extract or generate model name from description.

    Args:
        description: API/model description

    Returns:
        Model name in PascalCase
    """
    import re

    # Try to extract English words
    english_words = re.findall(r"[A-Za-z]+", description)
    if english_words:
        # Filter common words
        common_words = {"api", "the", "a", "an", "for", "to", "and", "or"}
        filtered = [w for w in english_words if w.lower() not in common_words]
        if filtered:
            return "".join(word.capitalize() for word in filtered[:2])

    # Generate from hash
    return f"Model{abs(hash(description)) % 1000}"


# Code generation prompt
API_GENERATION_PROMPT = """基于以下需求，生成 FastAPI 后端代码。

## 需求描述
{description}

## 技术要求
- 框架: FastAPI
- ORM: SQLAlchemy 2.0 (async)
- 验证: Pydantic v2
- 数据库: PostgreSQL

## 约束条件
{constraints}

## 需要生成的文件
{required_files}

请输出完整的代码，包括：
1. API 路由
2. 数据模型 (SQLAlchemy Model)
3. Schema (Pydantic)
4. Repository (可选)
"""