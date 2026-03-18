"""Base classes for framework-agnostic code generation.

This module provides the abstract base classes for code generators that
can produce framework-specific code from business model definitions.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class GeneratedFileType(Enum):
    """Types of generated files."""

    MODEL = "model"
    SCHEMA = "schema"
    REPOSITORY = "repository"
    SERVICE = "service"
    ROUTER = "router"
    ENDPOINT = "endpoint"
    MIGRATION = "migration"
    TEST = "test"
    CONFIG = "config"
    DOCS = "docs"


@dataclass
class GeneratedFile:
    """Represents a generated file.

    Attributes:
        file_type: Type of the generated file
        file_name: Name of the file
        file_path: Relative path from project root
        content: File content
        overwrite: Whether to overwrite existing file
        dependencies: List of required packages/modules
        imports: List of import statements
        metadata: Additional metadata
    """

    file_type: GeneratedFileType
    file_name: str
    file_path: str
    content: str
    overwrite: bool = True
    dependencies: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationContext:
    """Context for code generation.

    Attributes:
        project_name: Name of the project
        output_dir: Base output directory
        framework: Target framework (fastapi, django, etc.)
        language: Target language (python, typescript, etc.)
        version: Framework version
        options: Additional generation options
    """

    project_name: str = "afsa"
    output_dir: Path = field(default_factory=lambda: Path("."))
    framework: str = "fastapi"
    language: str = "python"
    version: str = "0.1.0"
    options: Dict[str, Any] = field(default_factory=dict)

    def get_output_path(self, file_path: str) -> Path:
        """Get full output path for a file."""
        return self.output_dir / file_path


class CodeGenerator(ABC):
    """Abstract base class for code generators.

    Subclasses implement framework-specific code generation logic.
    """

    def __init__(self, context: GenerationContext):
        self.context = context

    @abstractmethod
    def generate_model(self, model: "BusinessModel") -> List[GeneratedFile]:
        """Generate model and schema files.

        Args:
            model: Business model definition

        Returns:
            List of generated files
        """
        pass

    @abstractmethod
    def generate_api(
        self,
        api: "APIInterface",
        model: Optional["BusinessModel"] = None,
    ) -> List[GeneratedFile]:
        """Generate API endpoint files.

        Args:
            api: API interface definition
            model: Optional associated business model

        Returns:
            List of generated files
        """
        pass

    @abstractmethod
    def generate_repository(
        self,
        model: "BusinessModel",
    ) -> List[GeneratedFile]:
        """Generate repository/data access layer files.

        Args:
            model: Business model definition

        Returns:
            List of generated files
        """
        pass

    @abstractmethod
    def generate_migration(
        self,
        model: "BusinessModel",
        operation: str = "create",
        revision_id: Optional[str] = None,
    ) -> List[GeneratedFile]:
        """Generate database migration file.

        Args:
            model: Business model definition
            operation: Migration operation (create, alter, drop)
            revision_id: Optional revision identifier

        Returns:
            List of generated files
        """
        pass

    def generate_test(
        self,
        model: "BusinessModel",
        test_type: str = "unit",
    ) -> List[GeneratedFile]:
        """Generate test files for a model.

        Args:
            model: Business model definition
            test_type: Type of test (unit, integration, e2e)

        Returns:
            List of generated files
        """
        # Default implementation returns empty list
        # Subclasses can override for framework-specific test generation
        return []

    @abstractmethod
    def generate_service(
        self,
        model: "BusinessModel",
    ) -> List[GeneratedFile]:
        """Generate service layer files.

        Args:
            model: Business model definition

        Returns:
            List of generated files
        """
        pass

    def generate_full_crud(
        self,
        model: "BusinessModel",
    ) -> List[GeneratedFile]:
        """Generate full CRUD implementation for a model.

        This generates model, schema, repository, service, API, and tests.

        Args:
            model: Business model definition

        Returns:
            List of all generated files
        """
        files = []

        # Generate model and schema
        files.extend(self.generate_model(model))

        # Generate repository
        files.extend(self.generate_repository(model))

        # Generate service
        files.extend(self.generate_service(model))

        # Generate migration
        files.extend(self.generate_migration(model, operation="create"))

        # Generate tests
        files.extend(self.generate_test(model))

        return files


class CodeGeneratorRegistry:
    """Registry for code generators.

    Allows registering and retrieving generators by framework name.
    """

    _generators: Dict[str, type] = {}

    @classmethod
    def register(cls, framework: str) -> callable:
        """Decorator to register a code generator.

        Args:
            framework: Framework name (e.g., "fastapi", "django")

        Returns:
            Decorator function
        """

        def decorator(generator_class: type) -> type:
            cls._generators[framework] = generator_class
            return generator_class

        return decorator

    @classmethod
    def get_generator(
        cls,
        framework: str,
        context: GenerationContext,
    ) -> Optional[CodeGenerator]:
        """Get a code generator for a framework.

        Args:
            framework: Framework name
            context: Generation context

        Returns:
            CodeGenerator instance or None if not found
        """
        generator_class = cls._generators.get(framework)
        if generator_class:
            return generator_class(context)
        return None

    @classmethod
    def list_frameworks(cls) -> List[str]:
        """List all registered frameworks."""
        return list(cls._generators.keys())


def write_generated_files(
    files: List[GeneratedFile],
    output_dir: Path,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Write generated files to disk.

    Args:
        files: List of generated files
        output_dir: Base output directory
        dry_run: If True, don't actually write files

    Returns:
        Summary of written files
    """
    summary = {
        "total": len(files),
        "written": 0,
        "skipped": 0,
        "errors": [],
        "files": [],
    }

    for file in files:
        file_path = output_dir / file.file_path

        try:
            # Check if file exists and shouldn't be overwritten
            if file_path.exists() and not file.overwrite:
                summary["skipped"] += 1
                continue

            if not dry_run:
                # Create parent directories
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Write file
                file_path.write_text(file.content, encoding="utf-8")

            summary["written"] += 1
            summary["files"].append(str(file_path))

        except Exception as e:
            summary["errors"].append({
                "file": str(file_path),
                "error": str(e),
            })

    return summary