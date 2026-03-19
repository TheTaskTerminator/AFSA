"""Tests for code generation module."""
import pytest
from pathlib import Path
import tempfile
import shutil

from app.agents.base import TaskCard
from app.generation.code_generator import (
    GeneratedFile,
    CodeGenerator,
    FastAPICodeGenerator,
)


class TestGeneratedFile:
    """Tests for GeneratedFile."""

    def test_basic_file(self):
        """Test creating a generated file."""
        file = GeneratedFile(
            path="models/user.py",
            content="# User model",
            overwrite=False,
            description="User model file",
        )

        assert file.path == "models/user.py"
        assert file.content == "# User model"
        assert file.overwrite is False
        assert file.description == "User model file"

    def test_file_save(self):
        """Test saving a generated file."""
        temp_dir = tempfile.mkdtemp()
        try:
            file = GeneratedFile(
                path="models/user.py",
                content="# User model\nclass User:\n    pass\n",
            )
            
            file.save(temp_dir)
            
            saved_path = Path(temp_dir) / "models" / "user.py"
            assert saved_path.exists()
            assert saved_path.read_text() == "# User model\nclass User:\n    pass\n"
        finally:
            shutil.rmtree(temp_dir)

    def test_file_repr(self):
        """Test file representation."""
        file = GeneratedFile(
            path="models/user.py",
            content="# " * 100,  # 200 characters
        )
        
        repr_str = repr(file)
        assert "GeneratedFile" in repr_str
        assert "models/user.py" in repr_str


class TestCodeGenerator:
    """Tests for CodeGenerator base class."""

    def test_abstract_methods(self):
        """Test that generate is abstract."""
        with pytest.raises(TypeError):
            CodeGenerator()

    def test_concrete_implementation(self):
        """Test concrete implementation."""
        class TestGenerator(CodeGenerator):
            def generate(self, task_card: TaskCard):
                return [GeneratedFile(path="test.py", content="# test")]
        
        generator = TestGenerator()
        assert isinstance(generator, CodeGenerator)


class TestFastAPICodeGenerator:
    """Tests for FastAPICodeGenerator."""

    def test_initialization(self):
        """Test FastAPI generator initialization."""
        generator = FastAPICodeGenerator()
        assert generator is not None
        assert isinstance(generator, CodeGenerator)

    def test_initialization_with_template_dir(self):
        """Test initialization with template directory."""
        temp_dir = tempfile.mkdtemp()
        try:
            generator = FastAPICodeGenerator(template_dir=Path(temp_dir))
            assert generator.env is not None
        finally:
            shutil.rmtree(temp_dir)

    def test_generate_method_exists(self):
        """Test that generate method is implemented."""
        generator = FastAPICodeGenerator()
        
        # Create a minimal task card
        task_card = TaskCard(
            id="test-123",
            type="feature",
            priority="medium",
            description="Test feature",
            requirements=[],
            constraints={},
        )
        
        # Should not raise (though may return empty list without templates)
        result = generator.generate(task_card)
        assert isinstance(result, list)


class TestCodeGenerationIntegration:
    """Integration tests for code generation."""

    def test_full_generation_flow(self):
        """Test complete generation flow."""
        temp_dir = tempfile.mkdtemp()
        try:
            # Create generator
            generator = FastAPICodeGenerator()
            
            # Create task card
            task_card = TaskCard(
                id="test-456",
                type="feature",
                priority="high",
                description="Add user management",
                requirements=[],
                constraints={"target_zone": "mutable"},
            )
            
            # Generate code
            files = generator.generate(task_card)
            
            # Verify results
            assert isinstance(files, list)
            
            # Save files
            for file in files:
                file.save(temp_dir)
            
            # Verify files were created
            if files:
                for file in files:
                    saved_path = Path(temp_dir) / file.path
                    assert saved_path.exists()
                    
        finally:
            shutil.rmtree(temp_dir)
