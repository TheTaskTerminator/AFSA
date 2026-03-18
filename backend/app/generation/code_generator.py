"""
AFSA Code Generator - 代码生成器

根据任务卡和需求规格自动生成代码。
支持多种目标框架和模板。
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional
from jinja2 import Environment, FileSystemLoader, BaseLoader

from app.agents.base import RequirementSpec, TaskCard


# ============= 生成的文件 =============

class GeneratedFile:
    """生成的文件"""
    
    def __init__(
        self,
        path: str,
        content: str,
        overwrite: bool = False,
        description: str = "",
    ):
        self.path = path
        self.content = content
        self.overwrite = overwrite
        self.description = description
    
    def save(self, base_dir: str) -> None:
        """保存文件
        
        Args:
            base_dir: 基础目录
        """
        full_path = Path(base_dir) / self.path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(self.content)
    
    def __repr__(self) -> str:
        return f"GeneratedFile(path={self.path}, size={len(self.content)} bytes)"


# ============= 代码生成器基类 =============

class CodeGenerator(ABC):
    """代码生成器基类"""
    
    def __init__(self, template_dir: Optional[Path] = None):
        """初始化生成器
        
        Args:
            template_dir: 模板目录
        """
        self.template_dir = template_dir
        self.env: Optional[Environment] = None
        
        if template_dir and template_dir.exists():
            self.env = Environment(loader=FileSystemLoader(template_dir))
    
    @abstractmethod
    def generate(self, task_card: TaskCard) -> List[GeneratedFile]:
        """生成代码
        
        Args:
            task_card: 任务卡
            
        Returns:
            生成的文件列表
        """
        pass
    
    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """渲染模板
        
        Args:
            template_name: 模板名称
            context: 渲染上下文
            
        Returns:
            渲染后的内容
        """
        if not self.env:
            raise ValueError("Template environment not initialized")
        
        template = self.env.get_template(template_name)
        return template.render(**context)


# ============= FastAPI 代码生成器 =============

class FastAPICodeGenerator(CodeGenerator):
    """FastAPI 代码生成器"""
    
    def generate(self, task_card: TaskCard) -> List[GeneratedFile]:
        """生成 FastAPI 代码
        
        Args:
            task_card: 任务卡
            
        Returns:
            生成的文件列表
        """
        files = []
        
        for req in task_card.requirements:
            if req.type == "model":
                files.extend(self._generate_model_files(req))
            elif req.type == "api":
                files.extend(self._generate_api_files(req))
            elif req.type == "ui":
                files.extend(self._generate_ui_files(req))
        
        # 如果没有具体需求，生成通用代码
        if not files:
            files = self._generate_generic_files(task_card)
        
        return files
    
    def _generate_model_files(self, req: RequirementSpec) -> List[GeneratedFile]:
        """生成模型文件"""
        files = []
        
        model_name = req.spec.get("name", "BaseModel")
        fields = req.spec.get("fields", [])
        
        # 生成 SQLAlchemy 模型
        if self.env:
            try:
                content = self.render_template("python/fastapi/model.py.j2", {
                    "model_name": model_name,
                    "fields": fields,
                })
            except Exception:
                # 模板不存在，使用内置模板
                content = self._generate_model_code(model_name, fields)
        else:
            content = self._generate_model_code(model_name, fields)
        
        files.append(GeneratedFile(
            path=f"app/models/{model_name.lower()}.py",
            content=content,
            description=f"Data model: {model_name}",
        ))
        
        # 生成 Pydantic Schema
        schema_content = self._generate_schema_code(model_name, fields)
        files.append(GeneratedFile(
            path=f"app/schemas/{model_name.lower()}.py",
            content=schema_content,
            description=f"Pydantic schema: {model_name}",
        ))
        
        return files
    
    def _generate_api_files(self, req: RequirementSpec) -> List[GeneratedFile]:
        """生成 API 文件"""
        files = []
        
        model_name = req.spec.get("model", "Base")
        endpoints = req.spec.get("endpoints", [])
        
        if self.env:
            try:
                content = self.render_template("python/fastapi/api.py.j2", {
                    "model_name": model_name,
                    "endpoints": endpoints,
                })
            except Exception:
                content = self._generate_api_code(model_name, endpoints)
        else:
            content = self._generate_api_code(model_name, endpoints)
        
        files.append(GeneratedFile(
            path=f"app/api/{model_name.lower()}_router.py",
            content=content,
            description=f"API router for {model_name}",
        ))
        
        return files
    
    def _generate_ui_files(self, req: RequirementSpec) -> List[GeneratedFile]:
        """生成 UI 文件"""
        files = []
        
        component_name = req.spec.get("name", "Component")
        component_type = req.spec.get("component_type", "page")
        
        # 生成 React 组件
        content = self._generate_react_component(component_name, component_type)
        
        files.append(GeneratedFile(
            path=f"frontend/src/components/{component_name}.tsx",
            content=content,
            description=f"React component: {component_name}",
        ))
        
        return files
    
    def _generate_generic_files(self, task_card: TaskCard) -> List[GeneratedFile]:
        """生成通用代码文件"""
        files = []
        
        # 根据任务描述生成基础结构
        description = task_card.description
        
        # 生成简单的服务层
        service_content = f'''"""
Service module for: {description}
"""

from typing import List, Optional


class Service:
    """Service class"""
    
    def __init__(self):
        pass
    
    async def list_items(self) -> List[dict]:
        """List all items"""
        return []
    
    async def get_item(self, item_id: str) -> Optional[dict]:
        """Get item by ID"""
        return None
    
    async def create_item(self, data: dict) -> dict:
        """Create new item"""
        return data
    
    async def update_item(self, item_id: str, data: dict) -> Optional[dict]:
        """Update item"""
        return data
    
    async def delete_item(self, item_id: str) -> bool:
        """Delete item"""
        return True
'''
        
        files.append(GeneratedFile(
            path="app/services/generic_service.py",
            content=service_content,
            description="Generic service layer",
        ))
        
        return files
    
    # ============= 内置代码模板 =============
    
    def _generate_model_code(self, model_name: str, fields: List[Dict]) -> str:
        """生成模型代码（内置模板）"""
        field_defs = []
        for field in fields:
            field_name = field.get("name", "id")
            field_type = field.get("type", "str")
            
            # 转换类型
            type_mapping = {
                "string": "str",
                "integer": "int",
                "float": "float",
                "boolean": "bool",
                "datetime": "datetime",
                "uuid": "UUID",
            }
            python_type = type_mapping.get(field_type, field_type)
            
            if field.get("primary_key"):
                field_defs.append(f"    {field_name}: UUID = Field(default_factory=uuid.uuid4)")
            elif field.get("default"):
                field_defs.append(f"    {field_name}: {python_type} = {field['default']}")
            else:
                field_defs.append(f"    {field_name}: {python_type}")
        
        code = f'''"""
Model: {model_name}
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class {model_name}(Base):
    """{model_name} model"""
    
    __tablename__ = "{model_name.lower()}s"
    
{chr(10).join(field_defs)}
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    def __repr__(self) -> str:
        return f"<{model_name}(id={{self.id}})>"
'''
        return code
    
    def _generate_schema_code(self, model_name: str, fields: List[Dict]) -> str:
        """生成 Pydantic Schema 代码"""
        field_defs = []
        for field in fields:
            field_name = field.get("name", "id")
            field_type = field.get("type", "str")
            
            type_mapping = {
                "string": "str",
                "integer": "int",
                "float": "float",
                "boolean": "bool",
                "datetime": "datetime",
                "uuid": "UUID",
            }
            python_type = type_mapping.get(field_type, field_type)
            
            if field.get("primary_key"):
                field_defs.append(f"    id: UUID")
            elif field.get("required", True):
                field_defs.append(f"    {field_name}: {python_type}")
            else:
                field_defs.append(f"    {field_name}: Optional[{python_type}] = None")
        
        code = f'''"""
Schema: {model_name}
"""

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class {model_name}Base(BaseModel):
    """Base schema for {model_name}"""
    
{chr(10).join(field_defs)}


class {model_name}Create({model_name}Base):
    """Schema for creating {model_name}"""
    pass


class {model_name}Update(BaseModel):
    """Schema for updating {model_name}"""
    
{chr(10).join([f"    {f.get('name', 'id')}: Optional[{type_mapping.get(f.get('type', 'str'), f.get('type', 'str'))}]" for f in fields])}


class {model_name}InDB({model_name}Base):
    """Schema for {model_name} in database"""
    
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True
'''
        return code
    
    def _generate_api_code(self, model_name: str, endpoints: List[Dict]) -> str:
        """生成 API 代码"""
        code = f'''"""
API Router: {model_name}
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from uuid import UUID

from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/{model_name.lower()}s", tags=["{model_name}"])


@router.get("/", response_model=List[dict])
async def list_{model_name.lower()}s(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List all {model_name.lower()}s"""
    # TODO: Implement list logic
    return []


@router.get("/{{item_id}}", response_model=dict)
async def get_{model_name.lower()}({{item_id}}: UUID, db: AsyncSession = Depends(get_db)):
    """Get {model_name} by ID"""
    # TODO: Implement get logic
    return {{"id": str(item_id)}}


@router.post("/", response_model=dict)
async def create_{model_name.lower()}({{model_name.lower()}}_data: dict, db: AsyncSession = Depends(get_db)):
    """Create new {model_name.lower()}"""
    # TODO: Implement create logic
    return {{model_name.lower()}}_data


@router.put("/{{item_id}}", response_model=dict)
async def update_{model_name.lower()}({{item_id}}: UUID, {{model_name.lower()}}_data: dict, db: AsyncSession = Depends(get_db)):
    """Update {model_name.lower()}"""
    # TODO: Implement update logic
    return {{model_name.lower()}}_data


@router.delete("/{{item_id}}", response_model=dict)
async def delete_{model_name.lower()}({{item_id}}: UUID, db: AsyncSession = Depends(get_db)):
    """Delete {model_name.lower()}"""
    # TODO: Implement delete logic
    return {{"status": "deleted"}}
'''
        return code
    
    def _generate_react_component(self, component_name: str, component_type: str) -> str:
        """生成 React 组件代码"""
        code = f'''import React, {{ useState, useEffect }} from 'react';

interface {component_name}Props {{
  // TODO: Define props
}}

const {component_name}: React.FC<{component_name}Props> = ({{}}) => {{
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);

  useEffect(() => {{
    // TODO: Fetch data on mount
    const fetchData = async () => {{
      setLoading(true);
      try {{
        // API call here
      }} catch (error) {{
        console.error('Error fetching data:', error);
      }} finally {{
        setLoading(false);
      }}
    }};

    fetchData();
  }}, []);

  if (loading) {{
    return <div>Loading...</div>;
  }}

  return (
    <div className="{component_name.lower()}">
      <h1>{component_name}</h1>
      {/* TODO: Implement component content */}}
    </div>
  );
}};

export default {component_name};
'''
        return code


# ============= 代码生成器工厂 =============

def get_code_generator(framework: str = "fastapi", template_dir: Optional[Path] = None) -> CodeGenerator:
    """获取代码生成器实例
    
    Args:
        framework: 目标框架 (fastapi, django, nestjs, etc.)
        template_dir: 模板目录
        
    Returns:
        代码生成器实例
    """
    generators = {
        "fastapi": FastAPICodeGenerator,
        # TODO: Add more generators
        # "django": DjangoCodeGenerator,
        # "nestjs": NestJSCodeGenerator,
    }
    
    generator_class = generators.get(framework.lower())
    if not generator_class:
        raise ValueError(f"Unknown framework: {framework}. Available: {list(generators.keys())}")
    
    return generator_class(template_dir=template_dir)


# ============= 批量代码生成 =============

class CodeGenerationResult:
    """代码生成结果"""
    
    def __init__(self, files: List[GeneratedFile]):
        self.files = files
        self.success_count = len(files)
        self.error_count = 0
        self.errors: List[str] = []
    
    def save_all(self, base_dir: str) -> None:
        """保存所有生成的文件
        
        Args:
            base_dir: 基础目录
        """
        for file in self.files:
            file.save(base_dir)
    
    def __repr__(self) -> str:
        return f"CodeGenerationResult({self.success_count} files)"


async def generate_code_from_task(
    task_card: TaskCard,
    framework: str = "fastapi",
    template_dir: Optional[Path] = None,
) -> CodeGenerationResult:
    """从任务卡生成代码
    
    Args:
        task_card: 任务卡
        framework: 目标框架
        template_dir: 模板目录
        
    Returns:
        代码生成结果
    """
    generator = get_code_generator(framework, template_dir)
    files = generator.generate(task_card)
    
    return CodeGenerationResult(files)
