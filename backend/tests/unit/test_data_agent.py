"""Unit tests for Data Agent."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.data_agent import (
    ColumnDefinition,
    DataAgent,
    DataChangeResult,
    DataSession,
    MigrationFile,
    MigrationStatus,
    MigrationType,
    SchemaAnalysis,
    SchemaChangeImpact,
    TableDefinition,
    ValidationResult,
)
from app.agents.base import AgentResponse, AgentType, TaskCard
from app.business.dsl import (
    BusinessModel,
    FieldDefinition,
    FieldType,
    IndexDefinition,
)


# ---------------------------------------------------------------------------
# ColumnDefinition Tests
# ---------------------------------------------------------------------------

class TestColumnDefinition:
    """Tests for ColumnDefinition."""

    def test_create_column(self):
        """Test creating a column definition."""
        col = ColumnDefinition(
            name="id",
            data_type="INTEGER",
            primary_key=True,
            nullable=False,
        )
        assert col.name == "id"
        assert col.data_type == "INTEGER"
        assert col.primary_key is True
        assert col.nullable is False

    def test_column_with_foreign_key(self):
        """Test column with foreign key."""
        col = ColumnDefinition(
            name="user_id",
            data_type="INTEGER",
            foreign_key="users.id",
        )
        assert col.foreign_key == "users.id"

    def test_column_with_default(self):
        """Test column with default value."""
        col = ColumnDefinition(
            name="status",
            data_type="VARCHAR(50)",
            default="'active'",
        )
        assert col.default == "'active'"


# ---------------------------------------------------------------------------
# TableDefinition Tests
# ---------------------------------------------------------------------------

class TestTableDefinition:
    """Tests for TableDefinition."""

    def test_create_table(self):
        """Test creating a table definition."""
        table = TableDefinition(
            name="users",
            columns=[
                ColumnDefinition(name="id", data_type="INTEGER", primary_key=True),
                ColumnDefinition(name="name", data_type="VARCHAR(255)"),
            ],
        )
        assert table.name == "users"
        assert len(table.columns) == 2

    def test_table_with_indexes(self):
        """Test table with indexes."""
        table = TableDefinition(
            name="users",
            columns=[ColumnDefinition(name="email", data_type="VARCHAR(255)")],
            indexes=[
                IndexDefinition(name="idx_email", fields=["email"], unique=True),
            ],
        )
        assert len(table.indexes) == 1


# ---------------------------------------------------------------------------
# MigrationFile Tests
# ---------------------------------------------------------------------------

class TestMigrationFile:
    """Tests for MigrationFile."""

    def test_create_migration(self):
        """Test creating a migration file."""
        migration = MigrationFile(
            revision_id="20240101_120000",
            name="create_users",
            migration_type=MigrationType.CREATE_TABLE,
            upgrade_sql="CREATE TABLE users (id INTEGER PRIMARY KEY);",
            downgrade_sql="DROP TABLE users;",
        )
        assert migration.revision_id == "20240101_120000"
        assert migration.migration_type == MigrationType.CREATE_TABLE
        assert migration.status == MigrationStatus.PENDING

    def test_migration_dependencies(self):
        """Test migration with dependencies."""
        migration = MigrationFile(
            revision_id="20240102_120000",
            name="add_user_email",
            migration_type=MigrationType.ADD_COLUMN,
            upgrade_sql="ALTER TABLE users ADD COLUMN email VARCHAR(255);",
            downgrade_sql="ALTER TABLE users DROP COLUMN email;",
            dependencies=["20240101_120000"],
        )
        assert len(migration.dependencies) == 1


# ---------------------------------------------------------------------------
# ValidationResult Tests
# ---------------------------------------------------------------------------

class TestValidationResult:
    """Tests for ValidationResult."""

    def test_valid_result(self):
        """Test valid validation result."""
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_invalid_result(self):
        """Test invalid validation result."""
        result = ValidationResult(
            is_valid=False,
            errors=["Column 'name' cannot be null"],
        )
        assert result.is_valid is False
        assert len(result.errors) == 1

    def test_result_with_warnings(self):
        """Test result with warnings."""
        result = ValidationResult(
            is_valid=True,
            warnings=["Index may be slow on large tables"],
        )
        assert len(result.warnings) == 1


# ---------------------------------------------------------------------------
# DataChangeResult Tests
# ---------------------------------------------------------------------------

class TestDataChangeResult:
    """Tests for DataChangeResult."""

    def test_successful_result(self):
        """Test successful data change result."""
        result = DataChangeResult(
            success=True,
            impact=SchemaChangeImpact.LOW,
            summary="Table created successfully",
        )
        assert result.success is True
        assert result.impact == SchemaChangeImpact.LOW

    def test_result_with_migration(self):
        """Test result with migration."""
        migration = MigrationFile(
            revision_id="001",
            name="create_users",
            migration_type=MigrationType.CREATE_TABLE,
            upgrade_sql="CREATE TABLE users (id INT);",
            downgrade_sql="DROP TABLE users;",
        )
        result = DataChangeResult(
            success=True,
            migration=migration,
            summary="Migration generated",
        )
        assert result.migration is not None


# ---------------------------------------------------------------------------
# DataAgent Tests
# ---------------------------------------------------------------------------

class TestDataAgent:
    """Tests for DataAgent class."""

    @pytest.fixture
    def agent(self):
        """Create DataAgent instance."""
        return DataAgent()

    def test_agent_type(self, agent):
        """Test agent type."""
        assert agent.agent_type == AgentType.DATA
        assert agent.name == "Data Agent"

    def test_get_or_create_session(self, agent):
        """Test session creation."""
        session = agent._get_or_create_session("test-session")
        assert session.session_id == "test-session"
        assert isinstance(session, DataSession)

    def test_session_persistence(self, agent):
        """Test session persistence."""
        session1 = agent._get_or_create_session("persist-test")
        session1.context["key"] = "value"

        session2 = agent._get_or_create_session("persist-test")
        assert session2.context["key"] == "value"

    def test_clear_session(self, agent):
        """Test clearing session."""
        agent._get_or_create_session("clear-test")
        result = agent.clear_session("clear-test")
        assert result is True
        assert "clear-test" not in agent._sessions

    def test_clear_nonexistent_session(self, agent):
        """Test clearing non-existent session."""
        result = agent.clear_session("nonexistent")
        assert result is False


class TestDataAgentOperationDetection:
    """Tests for operation detection."""

    @pytest.fixture
    def agent(self):
        """Create DataAgent instance."""
        return DataAgent()

    def test_detect_schema_design(self, agent):
        """Test detecting schema design operation."""
        msg = "I need to design a new table for storing user profiles"
        op_type = agent._detect_operation_type(msg)
        assert op_type == "schema_design"

    def test_detect_migration(self, agent):
        """Test detecting migration operation."""
        msg = "Please create a migration to add email column"
        op_type = agent._detect_operation_type(msg)
        assert op_type == "migration"

    def test_detect_validation(self, agent):
        """Test detecting validation operation."""
        msg = "Validate the data changes before applying"
        op_type = agent._detect_operation_type(msg)
        assert op_type == "validation"

    def test_detect_optimization(self, agent):
        """Test detecting optimization operation."""
        msg = "This query is very slow, can you optimize it?"
        op_type = agent._detect_operation_type(msg)
        assert op_type == "optimization"

    def test_detect_default_schema_change(self, agent):
        """Test default to schema change."""
        msg = "Add a new column to the users table"
        op_type = agent._detect_operation_type(msg)
        assert op_type == "schema_change"


class TestDataAgentSQLGeneration:
    """Tests for SQL generation."""

    @pytest.fixture
    def agent(self):
        """Create DataAgent instance."""
        return DataAgent()

    def test_field_to_sql_column(self, agent):
        """Test field to SQL column conversion."""
        field = FieldDefinition(
            name="id",
            field_type=FieldType.INTEGER,
            primary_key=True,
            auto_increment=True,
        )
        sql = agent._field_to_sql_column(field)
        assert "id" in sql
        assert "INTEGER" in sql
        assert "PRIMARY KEY" in sql

    def test_field_to_sql_column_varchar(self, agent):
        """Test varchar field conversion."""
        field = FieldDefinition(
            name="email",
            field_type=FieldType.EMAIL,
            required=True,
        )
        sql = agent._field_to_sql_column(field)
        assert "email" in sql
        assert "VARCHAR" in sql

    def test_field_to_sql_column_nullable(self, agent):
        """Test nullable field conversion."""
        field = FieldDefinition(
            name="bio",
            field_type=FieldType.TEXT,
            nullable=True,
        )
        sql = agent._field_to_sql_column(field)
        # Nullable fields shouldn't have NOT NULL
        assert "NOT NULL" not in sql or field.nullable

    def test_generate_create_table_sql(self, agent):
        """Test CREATE TABLE SQL generation."""
        model = BusinessModel(
            name="User",
            table_name="users",
            fields=[
                FieldDefinition(name="id", field_type=FieldType.INTEGER, primary_key=True),
                FieldDefinition(name="name", field_type=FieldType.STRING, required=True),
            ],
        )
        sql = agent._generate_create_table_sql(model)
        assert "CREATE TABLE users" in sql
        assert "id" in sql
        assert "name" in sql

    def test_generate_drop_table_sql(self, agent):
        """Test DROP TABLE SQL generation."""
        model = BusinessModel(name="User", table_name="users")
        sql = agent._generate_drop_table_sql(model)
        assert "DROP TABLE IF EXISTS users" in sql

    def test_get_sql_type(self, agent):
        """Test SQL type mapping."""
        assert agent._get_sql_type(
            FieldDefinition(name="test", field_type=FieldType.INTEGER)
        ) == "INTEGER"
        assert agent._get_sql_type(
            FieldDefinition(name="test", field_type=FieldType.BOOLEAN)
        ) == "BOOLEAN"
        assert "VARCHAR" in agent._get_sql_type(
            FieldDefinition(name="test", field_type=FieldType.STRING)
        )

    def test_format_default_string(self, agent):
        """Test formatting string default."""
        assert agent._format_default("test") == "'test'"

    def test_format_default_boolean(self, agent):
        """Test formatting boolean default."""
        assert agent._format_default(True) == "TRUE"
        assert agent._format_default(False) == "FALSE"

    def test_format_default_none(self, agent):
        """Test formatting None default."""
        assert agent._format_default(None) == "NULL"


class TestDataAgentImpactAssessment:
    """Tests for impact assessment."""

    @pytest.fixture
    def agent(self):
        """Create DataAgent instance."""
        return DataAgent()

    def test_drop_table_breaking(self, agent):
        """Test drop table is breaking."""
        change = {"type": "table", "operation": "drop"}
        impact = agent._assess_impact(change)
        assert impact == SchemaChangeImpact.BREAKING

    def test_create_table_low_impact(self, agent):
        """Test create table is low impact."""
        change = {"type": "table", "operation": "create"}
        impact = agent._assess_impact(change)
        assert impact == SchemaChangeImpact.LOW

    def test_alter_table_with_not_null_high(self, agent):
        """Test alter with NOT NULL is high impact."""
        change = {
            "type": "column",
            "operation": "alter",
            "fields": [{"name": "status", "nullable": False}],
        }
        impact = agent._assess_impact(change)
        assert impact == SchemaChangeImpact.HIGH

    def test_alter_table_medium(self, agent):
        """Test alter table is medium impact."""
        change = {"type": "column", "operation": "alter", "fields": []}
        impact = agent._assess_impact(change)
        assert impact == SchemaChangeImpact.MEDIUM


class TestDataAgentModelConversion:
    """Tests for model conversion."""

    @pytest.fixture
    def agent(self):
        """Create DataAgent instance."""
        return DataAgent()

    def test_dict_to_model(self, agent):
        """Test converting dict to BusinessModel."""
        data = {
            "name": "Product",
            "table_name": "products",
            "description": "Product catalog",
            "fields": [
                {"name": "id", "type": "integer", "primary_key": True},
                {"name": "name", "type": "string", "required": True},
            ],
        }
        model = agent._dict_to_model(data)
        assert model.name == "Product"
        assert model.table_name == "products"
        assert len(model.fields) == 2

    def test_dict_to_model_unknown_type_defaults_to_string(self, agent):
        """Test unknown field type defaults to string."""
        data = {
            "name": "Test",
            "table_name": "tests",
            "fields": [
                {"name": "field", "type": "unknown_type"},
            ],
        }
        model = agent._dict_to_model(data)
        assert model.fields[0].field_type == FieldType.STRING


class TestDataAgentResponseFormatting:
    """Tests for response formatting."""

    @pytest.fixture
    def agent(self):
        """Create DataAgent instance."""
        return DataAgent()

    def test_format_schema_analysis(self, agent):
        """Test formatting schema analysis."""
        analysis = SchemaAnalysis(
            table_definitions=[
                TableDefinition(name="users", columns=[
                    ColumnDefinition(name="id", data_type="INTEGER"),
                ]),
            ],
            recommendations=["Add index on email"],
        )
        result = agent._format_schema_analysis(analysis)
        assert "users" in result
        assert "Add index" in result

    def test_format_data_change_result(self, agent):
        """Test formatting data change result."""
        result = DataChangeResult(
            success=True,
            impact=SchemaChangeImpact.LOW,
            summary="Table created",
            recommendations=["Run migration"],
        )
        output = agent._format_data_change_result(result)
        assert "成功" in output
        assert "low" in output

    def test_format_validation_result(self, agent):
        """Test formatting validation result."""
        result = ValidationResult(
            is_valid=False,
            errors=["Missing required field"],
            warnings=["Large table may be slow"],
        )
        output = agent._format_validation_result(result)
        assert "失败" in output
        assert "Missing required field" in output

    def test_summarize_results(self, agent):
        """Test summarizing results."""
        results = [
            DataChangeResult(success=True, summary="Created table A"),
            DataChangeResult(success=False, summary="Failed to create table B"),
        ]
        summary = agent._summarize_results(results)
        assert "1/2" in summary
        assert "Created table A" in summary


# ---------------------------------------------------------------------------
# Integration Tests with Mocked LLM
# ---------------------------------------------------------------------------

class TestDataAgentWithMockedLLM:
    """Tests with mocked LLM."""

    @pytest.fixture
    def agent_with_mocked_llm(self):
        """Create DataAgent with mocked LLM."""
        agent = DataAgent()
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock()
        agent._llm = mock_llm
        return agent

    @pytest.mark.asyncio
    async def test_process_message_schema_design(self, agent_with_mocked_llm):
        """Test processing schema design message."""
        agent = agent_with_mocked_llm
        agent.llm.chat.return_value = MagicMock(
            content="Tables:\n- users (id, name, email)\nRecommendations:\n- Add indexes"
        )

        response = await agent.process_message(
            session_id="test",
            message="Design a user table",
        )

        assert response.success is True
        assert "session_id" in response.metadata

    @pytest.mark.asyncio
    async def test_process_message_validation(self, agent_with_mocked_llm):
        """Test processing validation message."""
        agent = agent_with_mocked_llm
        agent.llm.chat.return_value = MagicMock(
            content="Validation passed. No issues found."
        )

        response = await agent.process_message(
            session_id="test",
            message="Validate these changes",
            context={"changes": {"operation": "add_column"}},
        )

        assert response.success is True

    @pytest.mark.asyncio
    async def test_generate_task_card(self, agent_with_mocked_llm):
        """Test generating task card."""
        agent = agent_with_mocked_llm

        # Create a session with a pending migration
        session = agent._get_or_create_session("task-test")
        session.migrations.append(MigrationFile(
            revision_id="001",
            name="create_users",
            migration_type=MigrationType.CREATE_TABLE,
            upgrade_sql="CREATE TABLE users (id INT);",
            downgrade_sql="DROP TABLE users;",
            status=MigrationStatus.PENDING,
        ))

        task_card = await agent.generate_task_card("task-test")
        assert task_card is not None
        # Check for Chinese "迁移" (migration) in description
        assert "迁移" in task_card.description or "migration" in task_card.description.lower()

    @pytest.mark.asyncio
    async def test_generate_task_card_no_migrations(self, agent_with_mocked_llm):
        """Test generating task card with no migrations."""
        agent = agent_with_mocked_llm
        agent._get_or_create_session("empty-session")

        task_card = await agent.generate_task_card("empty-session")
        assert task_card is None

    @pytest.mark.asyncio
    async def test_execute_task(self, agent_with_mocked_llm):
        """Test executing a task."""
        agent = agent_with_mocked_llm

        task_card = TaskCard(
            id="task-1",
            type="config",
            priority="high",
            description="Apply database changes",
            structured_requirements=[],
            constraints={
                "model_changes": [
                    {"operation": "create", "name": "products", "fields": []}
                ]
            },
        )

        response = await agent.execute(task_card)
        assert response.task_card is not None


# ---------------------------------------------------------------------------
# Migration Generation Tests
# ---------------------------------------------------------------------------

class TestMigrationGeneration:
    """Tests for migration generation."""

    @pytest.fixture
    def agent(self):
        """Create DataAgent instance."""
        return DataAgent()

    @pytest.mark.asyncio
    async def test_generate_migration_create(self, agent):
        """Test generating create table migration."""
        model = BusinessModel(
            name="Category",
            table_name="categories",
            fields=[
                FieldDefinition(name="id", field_type=FieldType.INTEGER, primary_key=True),
                FieldDefinition(name="name", field_type=FieldType.STRING, required=True),
            ],
        )

        migration = await agent.generate_migration(model, operation="create")
        assert migration.migration_type == MigrationType.CREATE_TABLE
        assert "categories" in migration.upgrade_sql
        # Check for Alembic style drop_table or raw SQL DROP TABLE
        assert "drop_table" in migration.downgrade_sql or "DROP TABLE" in migration.downgrade_sql

    @pytest.mark.asyncio
    async def test_generate_migration_drop(self, agent):
        """Test generating drop table migration."""
        model = BusinessModel(
            name="OldTable",
            table_name="old_tables",
        )

        migration = await agent.generate_migration(model, operation="drop")
        assert migration.migration_type == MigrationType.DROP_TABLE
        # Check for Alembic style drop_table or raw SQL DROP TABLE
        assert "drop_table" in migration.upgrade_sql or "DROP TABLE" in migration.upgrade_sql
        # Downgrade should have create_table
        assert "create_table" in migration.downgrade_sql or "CREATE TABLE" in migration.downgrade_sql

    @pytest.mark.asyncio
    async def test_generate_migration_with_revision(self, agent):
        """Test generating migration with custom revision."""
        model = BusinessModel(name="Test", table_name="tests")

        migration = await agent.generate_migration(
            model,
            operation="create",
            revision_id="custom_rev_001",
        )
        assert migration.revision_id == "custom_rev_001"


# ---------------------------------------------------------------------------
# Data Validation Tests
# ---------------------------------------------------------------------------

class TestDataValidation:
    """Tests for data validation."""

    @pytest.fixture
    def agent_with_llm(self):
        """Create agent with mocked LLM."""
        agent = DataAgent()
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock()
        agent._llm = mock_llm
        return agent

    @pytest.mark.asyncio
    async def test_validate_data_changes_success(self, agent_with_llm):
        """Test successful validation."""
        agent = agent_with_llm
        agent.llm.chat.return_value = MagicMock(
            content="Validation passed. All constraints satisfied."
        )

        result = await agent.validate_data_changes(
            changes={"operation": "add_column"},
        )

        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_validate_data_changes_with_errors(self, agent_with_llm):
        """Test validation with errors."""
        agent = agent_with_llm
        agent.llm.chat.return_value = MagicMock(
            content="Errors found:\n- Missing required field\n- Invalid data type"
        )

        result = await agent.validate_data_changes(
            changes={"operation": "alter"},
        )

        assert result.is_valid is False


# ---------------------------------------------------------------------------
# Schema Change Processing Tests
# ---------------------------------------------------------------------------

class TestSchemaChangeProcessing:
    """Tests for schema change processing."""

    @pytest.fixture
    def agent(self):
        """Create DataAgent instance."""
        return DataAgent()

    def test_generate_change_recommendations_breaking(self, agent):
        """Test recommendations for breaking change."""
        recommendations = agent._generate_change_recommendations(
            change={"operation": "drop"},
            impact=SchemaChangeImpact.BREAKING,
            validation=ValidationResult(is_valid=True),
        )
        assert any("breaking" in r.lower() or "崩溃" in r for r in recommendations)

    def test_generate_change_recommendations_high_impact(self, agent):
        """Test recommendations for high impact change."""
        recommendations = agent._generate_change_recommendations(
            change={"operation": "alter"},
            impact=SchemaChangeImpact.HIGH,
            validation=ValidationResult(is_valid=True),
        )
        assert any("锁定" in r or "lock" in r.lower() for r in recommendations)

    def test_generate_change_summary(self, agent):
        """Test change summary generation."""
        summary = agent._generate_change_summary(
            change={"operation": "create", "name": "orders"},
            validation=ValidationResult(is_valid=True),
        )
        assert "orders" in summary
        assert "成功" in summary

    def test_generate_change_summary_with_errors(self, agent):
        """Test change summary with errors."""
        summary = agent._generate_change_summary(
            change={"operation": "alter", "name": "users"},
            validation=ValidationResult(
                is_valid=False,
                errors=["Error 1", "Error 2"],
            ),
        )
        assert "2" in summary or "错误" in summary