"""Tests for code generation module."""
import pytest
from pathlib import Path

from app.business.dsl import (
    APIInterface,
    BusinessModel,
    EndpointDefinition,
    FieldDefinition,
    FieldType,
    HTTPMethod,
    IndexDefinition,
    ParameterDefinition,
    ParameterLocation,
    RelationshipDefinition,
    RelationshipType,
    ValidationRule,
    id_field,
    name_field,
    email_field,
    created_at_field,
    updated_at_field,
    list_endpoint,
    get_endpoint,
)
from app.generation import (
    CodeGeneratorRegistry,
    GeneratedFile,
    GeneratedFileType,
    GenerationContext,
    FastAPIGenerator,
    write_generated_files,
)


class TestGeneratedFile:
    """Tests for GeneratedFile."""

    def test_basic_file(self):
        """Test creating a generated file."""
        file = GeneratedFile(
            file_type=GeneratedFileType.MODEL,
            file_name="user.py",
            file_path="models/user.py",
            content="# User model",
        )

        assert file.file_type == GeneratedFileType.MODEL
        assert file.file_name == "user.py"
        assert file.overwrite is True
        assert file.dependencies == []

    def test_file_with_dependencies(self):
        """Test file with dependencies."""
        file = GeneratedFile(
            file_type=GeneratedFileType.SCHEMA,
            file_name="user_schema.py",
            file_path="schemas/user_schema.py",
            content="# User schema",
            dependencies=["pydantic>=2.0.0", "sqlalchemy>=2.0.0"],
        )

        assert len(file.dependencies) == 2
        assert "pydantic>=2.0.0" in file.dependencies


class TestGenerationContext:
    """Tests for GenerationContext."""

    def test_default_context(self):
        """Test default context values."""
        context = GenerationContext()

        assert context.project_name == "afsa"
        assert context.framework == "fastapi"
        assert context.language == "python"

    def test_custom_context(self):
        """Test custom context values."""
        context = GenerationContext(
            project_name="myapp",
            output_dir=Path("/tmp/output"),
            framework="fastapi",
        )

        assert context.project_name == "myapp"
        assert context.output_dir == Path("/tmp/output")

    def test_get_output_path(self):
        """Test output path resolution."""
        context = GenerationContext(output_dir=Path("/tmp/output"))

        path = context.get_output_path("models/user.py")

        assert path == Path("/tmp/output/models/user.py")


class TestCodeGeneratorRegistry:
    """Tests for CodeGeneratorRegistry."""

    def test_registered_frameworks(self):
        """Test that FastAPI is registered."""
        frameworks = CodeGeneratorRegistry.list_frameworks()

        assert "fastapi" in frameworks

    def test_get_generator(self):
        """Test getting a generator."""
        context = GenerationContext()
        generator = CodeGeneratorRegistry.get_generator("fastapi", context)

        assert generator is not None
        assert isinstance(generator, FastAPIGenerator)

    def test_get_nonexistent_generator(self):
        """Test getting a nonexistent generator."""
        context = GenerationContext()
        generator = CodeGeneratorRegistry.get_generator("nonexistent", context)

        assert generator is None


class TestFastAPIGenerator:
    """Tests for FastAPIGenerator."""

    @pytest.fixture
    def generator(self):
        """Create a FastAPI generator."""
        context = GenerationContext()
        return FastAPIGenerator(context)

    @pytest.fixture
    def sample_model(self):
        """Create a sample business model."""
        return (
            BusinessModel(
                name="User",
                table_name="users",
                description="Application user",
            )
            .add_field(id_field())
            .add_field(name_field())
            .add_field(email_field())
            .add_field(created_at_field())
            .add_field(updated_at_field())
            .add_index(
                IndexDefinition(
                    name="idx_user_email",
                    fields=["email"],
                    unique=True,
                )
            )
        )

    @pytest.fixture
    def sample_api(self):
        """Create a sample API interface."""
        return APIInterface(
            name="UserAPI",
            base_path="/api/v1/users",
            endpoints=[
                list_endpoint("users", "/api/v1/users", {"type": "array"}),
                get_endpoint("user", "/api/v1/users/{id}", {"type": "object"}),
            ],
        )

    def test_generate_model(self, generator, sample_model):
        """Test generating model files."""
        files = generator.generate_model(sample_model)

        assert len(files) >= 1
        assert any(f.file_type == GeneratedFileType.MODEL for f in files)

        # Check model file content
        model_file = next(f for f in files if f.file_type == GeneratedFileType.MODEL)
        assert "class User(Base)" in model_file.content
        assert "__tablename__ = \"users\"" in model_file.content

    def test_generate_repository(self, generator, sample_model):
        """Test generating repository file."""
        files = generator.generate_repository(sample_model)

        assert len(files) == 1

        repo_file = files[0]
        assert repo_file.file_type == GeneratedFileType.REPOSITORY
        assert "UserRepository" in repo_file.content
        assert "def create" in repo_file.content
        assert "def get_by_id" in repo_file.content

    def test_generate_service(self, generator, sample_model):
        """Test generating service file."""
        files = generator.generate_service(sample_model)

        assert len(files) == 1

        service_file = files[0]
        assert service_file.file_type == GeneratedFileType.SERVICE
        assert "UserService" in service_file.content
        assert "def create" in service_file.content
        assert "def get_list" in service_file.content

    def test_generate_api(self, generator, sample_api, sample_model):
        """Test generating API router."""
        files = generator.generate_api(sample_api, sample_model)

        assert len(files) == 1

        router_file = files[0]
        assert router_file.file_type == GeneratedFileType.ROUTER
        assert "router = APIRouter" in router_file.content
        assert "list_users" in router_file.content

    def test_generate_migration(self, generator, sample_model):
        """Test generating migration file."""
        files = generator.generate_migration(sample_model, operation="create")

        assert len(files) == 1

        migration_file = files[0]
        assert migration_file.file_type == GeneratedFileType.MIGRATION
        assert "def upgrade" in migration_file.content
        assert "def downgrade" in migration_file.content
        assert "op.create_table" in migration_file.content

    def test_generate_test(self, generator, sample_model):
        """Test generating test files."""
        files = generator.generate_test(sample_model, test_type="unit")

        assert len(files) >= 1

        test_file = files[0]
        assert test_file.file_type == GeneratedFileType.TEST
        assert "TestUserService" in test_file.content

    def test_generate_full_crud(self, generator, sample_model):
        """Test generating full CRUD implementation."""
        files = generator.generate_full_crud(sample_model)

        assert len(files) >= 4

        file_types = {f.file_type for f in files}
        assert GeneratedFileType.MODEL in file_types
        assert GeneratedFileType.REPOSITORY in file_types
        assert GeneratedFileType.SERVICE in file_types
        assert GeneratedFileType.MIGRATION in file_types


class TestWriteGeneratedFiles:
    """Tests for write_generated_files function."""

    def test_dry_run(self, tmp_path):
        """Test dry run doesn't write files."""
        files = [
            GeneratedFile(
                file_type=GeneratedFileType.MODEL,
                file_name="test.py",
                file_path="models/test.py",
                content="# Test",
            )
        ]

        summary = write_generated_files(files, tmp_path, dry_run=True)

        assert summary["total"] == 1
        assert summary["written"] == 1
        assert not (tmp_path / "models" / "test.py").exists()

    def test_write_files(self, tmp_path):
        """Test writing files."""
        files = [
            GeneratedFile(
                file_type=GeneratedFileType.MODEL,
                file_name="test.py",
                file_path="models/test.py",
                content="# Test content",
            )
        ]

        summary = write_generated_files(files, tmp_path, dry_run=False)

        assert summary["written"] == 1
        assert (tmp_path / "models" / "test.py").exists()
        assert (tmp_path / "models" / "test.py").read_text() == "# Test content"

    def test_skip_existing(self, tmp_path):
        """Test skipping existing files."""
        # Create existing file
        existing_path = tmp_path / "models" / "test.py"
        existing_path.parent.mkdir(parents=True)
        existing_path.write_text("# Existing")

        files = [
            GeneratedFile(
                file_type=GeneratedFileType.MODEL,
                file_name="test.py",
                file_path="models/test.py",
                content="# New content",
                overwrite=False,
            )
        ]

        summary = write_generated_files(files, tmp_path, dry_run=False)

        assert summary["skipped"] == 1
        assert existing_path.read_text() == "# Existing"

    def test_overwrite_existing(self, tmp_path):
        """Test overwriting existing files."""
        # Create existing file
        existing_path = tmp_path / "models" / "test.py"
        existing_path.parent.mkdir(parents=True)
        existing_path.write_text("# Existing")

        files = [
            GeneratedFile(
                file_type=GeneratedFileType.MODEL,
                file_name="test.py",
                file_path="models/test.py",
                content="# New content",
                overwrite=True,
            )
        ]

        summary = write_generated_files(files, tmp_path, dry_run=False)

        assert summary["written"] == 1
        assert existing_path.read_text() == "# New content"


class TestModelWithRelationships:
    """Tests for models with relationships."""

    @pytest.fixture
    def generator(self):
        """Create a FastAPI generator."""
        context = GenerationContext()
        return FastAPIGenerator(context)

    @pytest.fixture
    def post_model(self):
        """Create a Post model with User relationship."""
        return (
            BusinessModel(
                name="Post",
                table_name="posts",
                description="Blog post",
            )
            .add_field(id_field())
            .add_field(name_field("title"))
            .add_field(
                FieldDefinition(
                    name="content",
                    field_type=FieldType.TEXT,
                    description="Post content",
                )
            )
            .add_field(
                FieldDefinition(
                    name="author_id",
                    field_type=FieldType.INTEGER,
                    foreign_key="users.id",
                )
            )
            .add_relationship(
                RelationshipDefinition(
                    name="author",
                    target_model="User",
                    relationship_type=RelationshipType.MANY_TO_ONE,
                    back_populates="posts",
                )
            )
        )

    def test_generate_model_with_relationships(self, generator, post_model):
        """Test generating model with relationships."""
        files = generator.generate_model(post_model)

        model_file = next(f for f in files if f.file_type == GeneratedFileType.MODEL)

        assert "relationship" in model_file.content
        assert "author" in model_file.content
        assert "ForeignKey" in model_file.content


class TestFieldTypes:
    """Tests for different field types."""

    @pytest.fixture
    def generator(self):
        """Create a FastAPI generator."""
        context = GenerationContext()
        return FastAPIGenerator(context)

    def test_uuid_field(self, generator):
        """Test UUID field generation."""
        model = BusinessModel(
            name="Document",
            table_name="documents",
            fields=[
                FieldDefinition(
                    name="id",
                    field_type=FieldType.UUID,
                    primary_key=True,
                ),
            ],
        )

        files = generator.generate_model(model)
        model_file = next(f for f in files if f.file_type == GeneratedFileType.MODEL)

        assert "UUID" in model_file.content

    def test_json_field(self, generator):
        """Test JSON field generation."""
        model = BusinessModel(
            name="Config",
            table_name="configs",
            fields=[
                id_field(),
                FieldDefinition(
                    name="data",
                    field_type=FieldType.JSON,
                    description="Configuration data",
                ),
            ],
        )

        files = generator.generate_model(model)
        model_file = next(f for f in files if f.file_type == GeneratedFileType.MODEL)

        assert "JSON" in model_file.content

    def test_decimal_field(self, generator):
        """Test Decimal field generation."""
        model = BusinessModel(
            name="Product",
            table_name="products",
            fields=[
                id_field(),
                FieldDefinition(
                    name="price",
                    field_type=FieldType.DECIMAL,
                    description="Product price",
                ),
            ],
        )

        files = generator.generate_model(model)
        model_file = next(f for f in files if f.file_type == GeneratedFileType.MODEL)

        assert "Numeric" in model_file.content