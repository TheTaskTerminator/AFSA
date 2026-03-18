"""Code generation module.

This module provides framework-agnostic code generation infrastructure.
"""
from app.generation.base import (
    CodeGenerator,
    CodeGeneratorRegistry,
    GeneratedFile,
    GeneratedFileType,
    GenerationContext,
    write_generated_files,
)
from app.generation.fastapi import FastAPIGenerator

__all__ = [
    # Base classes
    "CodeGenerator",
    "CodeGeneratorRegistry",
    "GeneratedFile",
    "GeneratedFileType",
    "GenerationContext",
    "write_generated_files",
    # Framework generators
    "FastAPIGenerator",
]