"""
AFSA Code Generation Package

代码生成模块：
- 支持多种目标框架 (FastAPI, Django, NestJS 等)
- 基于模板的代码生成
- 结构化需求转换
"""

from app.generation.code_generator import (
    CodeGenerator,
    FastAPICodeGenerator,
    GeneratedFile,
    CodeGenerationResult,
    get_code_generator,
    generate_code_from_task,
)

__all__ = [
    "CodeGenerator",
    "FastAPICodeGenerator",
    "GeneratedFile",
    "CodeGenerationResult",
    "get_code_generator",
    "generate_code_from_task",
]
