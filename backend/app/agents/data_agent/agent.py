"""Data Agent implementation for database schema design and migration management."""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from app.agents.base import AgentResponse, AgentType, BaseAgent, TaskCard
from app.agents.llm import BaseLLM, ChatMessage, get_llm
from app.agents.data_agent.prompts import (
    DATA_SYSTEM_PROMPT,
    get_system_prompt,
    format_schema_design_prompt,
    format_migration_generation_prompt,
    format_data_validation_prompt,
    format_query_optimization_prompt,
    format_migration_review_prompt,
)
from app.business.dsl import (
    BusinessModel,
    FieldDefinition,
    FieldType,
    IndexDefinition,
    RelationshipDefinition,
)
from app.generation.base import GeneratedFile, CodeGeneratorRegistry, GenerationContext

logger = logging.getLogger(__name__)


class MigrationType(str, Enum):
    """Types of database migrations."""

    CREATE_TABLE = "create_table"
    ALTER_TABLE = "alter_table"
    DROP_TABLE = "drop_table"
    ADD_COLUMN = "add_column"
    DROP_COLUMN = "drop_column"
    MODIFY_COLUMN = "modify_column"
    ADD_INDEX = "add_index"
    DROP_INDEX = "drop_index"
    ADD_CONSTRAINT = "add_constraint"
    DROP_CONSTRAINT = "drop_constraint"
    DATA_MIGRATION = "data_migration"


class MigrationStatus(str, Enum):
    """Status of a migration."""

    PENDING = "pending"
    VALIDATED = "validated"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"


class SchemaChangeImpact(str, Enum):
    """Impact level of schema changes."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BREAKING = "breaking"


@dataclass
class ColumnDefinition:
    """Database column definition."""

    name: str
    data_type: str
    nullable: bool = True
    default: Optional[str] = None
    primary_key: bool = False
    unique: bool = False
    foreign_key: Optional[str] = None
    check_constraint: Optional[str] = None
    comment: Optional[str] = None


@dataclass
class TableDefinition:
    """Database table definition."""

    name: str
    columns: List[ColumnDefinition] = field(default_factory=list)
    indexes: List[IndexDefinition] = field(default_factory=list)
    primary_key: Optional[List[str]] = None
    foreign_keys: Dict[str, str] = field(default_factory=dict)  # col -> ref_table.ref_col
    check_constraints: List[str] = field(default_factory=list)
    comment: Optional[str] = None


@dataclass
class MigrationFile:
    """Represents a generated migration file."""

    revision_id: str
    name: str
    migration_type: MigrationType
    upgrade_sql: str
    downgrade_sql: str
    status: MigrationStatus = MigrationStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of data validation."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    affected_rows: int = 0
    data_integrity_issues: List[str] = field(default_factory=list)


@dataclass
class SchemaAnalysis:
    """Result of schema analysis."""

    table_definitions: List[TableDefinition] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    indexes: List[IndexDefinition] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    performance_issues: List[str] = field(default_factory=list)


@dataclass
class DataChangeResult:
    """Result of a data change operation."""

    success: bool
    migration: Optional[MigrationFile] = None
    validation: Optional[ValidationResult] = None
    impact: SchemaChangeImpact = SchemaChangeImpact.NONE
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)


@dataclass
class DataSession:
    """Session for data agent operations."""

    session_id: str
    model_changes: List[Dict[str, Any]] = field(default_factory=list)
    migrations: List[MigrationFile] = field(default_factory=list)
    validations: List[ValidationResult] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    messages: List[Dict[str, str]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class DataAgent(BaseAgent):
    """Data Agent for database schema design and migration management.

    The Data Agent is responsible for:
    1. Database schema design and optimization
    2. Migration script generation (create, alter, drop)
    3. Data change validation and verification
    4. Query optimization recommendations

    It works with other agents to ensure database changes are safe,
    performant, and follow best practices.

    Attributes:
        agent_type: Always AgentType.DATA for data agent
        name: Agent name for identification
        llm: LLM instance for analysis
    """

    agent_type = AgentType.DATA
    name = "Data Agent"

    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize Data Agent.

        Args:
            llm: LLM instance (will use default if not provided)
            config: Agent configuration
        """
        self._llm = llm
        self._config = config or {}
        self._sessions: Dict[str, DataSession] = {}

    @property
    def llm(self) -> BaseLLM:
        """Get LLM instance."""
        if self._llm is None:
            self._llm = get_llm()
        return self._llm

    def _get_or_create_session(self, session_id: str) -> DataSession:
        """Get existing session or create new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = DataSession(session_id=session_id)
        return self._sessions[session_id]

    async def process_message(
        self,
        session_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Process a message for database operations.

        Args:
            session_id: Session identifier
            message: Message describing database changes
            context: Additional context (models, constraints, etc.)

        Returns:
            AgentResponse with operation results
        """
        session = self._get_or_create_session(session_id)

        # Update context
        if context:
            session.context.update(context)

        # Add to message history
        session.messages.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.utcnow().isoformat(),
        })

        try:
            # Parse the request to determine operation type
            operation_type = self._detect_operation_type(message)

            if operation_type == "schema_design":
                result = await self._handle_schema_design(message, session.context)
            elif operation_type == "migration":
                result = await self._handle_migration_request(message, session.context)
            elif operation_type == "validation":
                result = await self._handle_validation_request(message, session.context)
            elif operation_type == "optimization":
                result = await self._handle_optimization_request(message, session.context)
            else:
                # Default: treat as schema change request
                result = await self._handle_schema_change(message, session.context)

            # Store result
            if isinstance(result, DataChangeResult):
                if result.migration:
                    session.migrations.append(result.migration)
                if result.validation:
                    session.validations.append(result.validation)

            # Format response
            response_content = self._format_response(result)

            # Add assistant message
            session.messages.append({
                "role": "assistant",
                "content": response_content,
                "timestamp": datetime.utcnow().isoformat(),
            })
            session.updated_at = datetime.utcnow()

            return AgentResponse(
                success=True,
                content=response_content,
                metadata={
                    "session_id": session_id,
                    "operation_type": operation_type,
                },
            )

        except Exception as e:
            logger.error(f"Data Agent error: {e}")
            return AgentResponse(
                success=False,
                content=f"数据库操作时出错：{str(e)}",
                metadata={"error": str(e), "session_id": session_id},
            )

    async def generate_task_card(self, session_id: str) -> Optional[TaskCard]:
        """Generate a task card from the session.

        Args:
            session_id: Session identifier

        Returns:
            TaskCard if operations were completed, None otherwise
        """
        session = self._sessions.get(session_id)

        if not session or not session.migrations:
            return None

        pending_migrations = [
            m for m in session.migrations
            if m.status == MigrationStatus.PENDING
        ]

        if not pending_migrations:
            return None

        task_card = TaskCard(
            id=str(uuid.uuid4()),
            type="config",
            priority="high",
            description=f"数据库迁移: {len(pending_migrations)} 个待处理迁移",
            structured_requirements=[
                {
                    "id": "migration-count",
                    "description": f"待处理迁移数: {len(pending_migrations)}",
                    "acceptance_criteria": "所有迁移已验证并批准",
                },
                {
                    "id": "migration-types",
                    "description": f"迁移类型: {', '.join(set(m.migration_type.value for m in pending_migrations))}",
                    "acceptance_criteria": "所有迁移类型已确认",
                },
            ],
            constraints={
                "migrations": [m.revision_id for m in pending_migrations],
            },
        )

        return task_card

    async def execute(self, task_card: TaskCard) -> AgentResponse:
        """Execute database operations for a task.

        Args:
            task_card: Task card with database change details

        Returns:
            AgentResponse with operation results
        """
        try:
            # Extract model changes from task card
            model_changes = task_card.constraints.get("model_changes", [])
            context = {
                "priority": task_card.priority,
                "requirements": task_card.structured_requirements,
                **task_card.constraints,
            }

            results = []
            for change in model_changes:
                result = await self.process_model_change(change, context)
                results.append(result)

            # Determine overall success
            success = all(r.success for r in results)
            summary = self._summarize_results(results)

            return AgentResponse(
                success=success,
                content=summary,
                metadata={
                    "results_count": len(results),
                    "migrations_generated": sum(
                        1 for r in results if r.migration is not None
                    ),
                },
                task_card=task_card,
            )

        except Exception as e:
            logger.error(f"Data Agent execution error: {e}")
            return AgentResponse(
                success=False,
                content=f"执行数据库操作失败：{str(e)}",
                metadata={"error": str(e)},
            )

    # -----------------------------------------------------------------------
    # Schema Design
    # -----------------------------------------------------------------------

    async def design_schema(
        self,
        requirements: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> SchemaAnalysis:
        """Design database schema from requirements.

        Args:
            requirements: Description of data requirements
            context: Additional context for design

        Returns:
            SchemaAnalysis with table definitions and recommendations
        """
        context = context or {}

        prompt = format_schema_design_prompt(
            requirements=requirements,
            context=json.dumps(context, ensure_ascii=False, indent=2),
        )

        messages = [
            ChatMessage(role="system", content=get_system_prompt()),
            ChatMessage(role="user", content=prompt),
        ]

        response = await self.llm.chat(messages, temperature=0.3)
        return self._parse_schema_analysis(response.content)

    def _parse_schema_analysis(self, content: str) -> SchemaAnalysis:
        """Parse LLM response into SchemaAnalysis."""
        analysis = SchemaAnalysis()

        # Extract table definitions
        tables = self._extract_tables(content)
        analysis.table_definitions = tables

        # Extract recommendations
        recommendations = []
        lines = content.split("\n")
        in_recommendations = False

        for line in lines:
            line_lower = line.lower()
            if "recommendation" in line_lower:
                in_recommendations = True
                continue

            if in_recommendations:
                if line.strip().startswith("-") or line.strip().startswith("*"):
                    recommendations.append(line.strip("- *").strip())
                elif line.strip() and not line.strip().startswith("#"):
                    # Check if we've moved to a new section
                    if any(
                        section in line_lower
                        for section in ["performance", "issue", "warning"]
                    ):
                        in_recommendations = False
                    else:
                        recommendations.append(line.strip())

        analysis.recommendations = recommendations[:10]  # Limit to 10

        return analysis

    def _extract_tables(self, content: str) -> List[TableDefinition]:
        """Extract table definitions from content."""
        tables = []

        # Look for table definitions in the content
        # Pattern: "Table: table_name" or "CREATE TABLE table_name"
        table_pattern = r"(?:Table:?\s*|CREATE TABLE\s+)(\w+)"
        matches = re.finditer(table_pattern, content, re.IGNORECASE)

        for match in matches:
            table_name = match.group(1)
            table = TableDefinition(name=table_name)

            # Try to extract columns (simplified)
            # Look for lines with column definitions
            start_pos = match.end()
            table_section = content[start_pos:start_pos + 500]  # Get next 500 chars

            col_pattern = r"(\w+)\s*:\s*(\w+(?:\([^)]+\))?)"
            for col_match in re.finditer(col_pattern, table_section):
                col_name = col_match.group(1)
                col_type = col_match.group(2)

                # Skip if this looks like a header or metadata
                if col_name.lower() in ("table", "column", "type", "description"):
                    continue

                table.columns.append(ColumnDefinition(
                    name=col_name,
                    data_type=col_type,
                ))

            if table.columns:
                tables.append(table)

        return tables

    # -----------------------------------------------------------------------
    # Migration Generation
    # -----------------------------------------------------------------------

    async def generate_migration(
        self,
        model: BusinessModel,
        operation: str = "create",
        revision_id: Optional[str] = None,
    ) -> MigrationFile:
        """Generate migration for a business model.

        Args:
            model: Business model to migrate
            operation: Operation type (create, alter, drop)
            revision_id: Optional revision ID

        Returns:
            MigrationFile with upgrade and downgrade SQL
        """
        # Use code generator if available
        generator = CodeGeneratorRegistry.get_generator(
            "fastapi",
            GenerationContext(),
        )

        if generator:
            files = generator.generate_migration(model, operation, revision_id)
            if files:
                file = files[0]
                return self._convert_generated_file_to_migration(
                    file, model, operation, revision_id
                )

        # Fallback: generate migration manually
        return self._generate_migration_manually(model, operation, revision_id)

    def _convert_generated_file_to_migration(
        self,
        file: GeneratedFile,
        model: BusinessModel,
        operation: str,
        revision_id: Optional[str],
    ) -> MigrationFile:
        """Convert GeneratedFile to MigrationFile."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        revision = revision_id or timestamp

        # Extract upgrade and downgrade from content
        upgrade_sql = self._extract_upgrade_sql(file.content)
        downgrade_sql = self._extract_downgrade_sql(file.content)

        migration_type = {
            "create": MigrationType.CREATE_TABLE,
            "alter": MigrationType.ALTER_TABLE,
            "drop": MigrationType.DROP_TABLE,
        }.get(operation, MigrationType.CREATE_TABLE)

        return MigrationFile(
            revision_id=revision,
            name=f"{operation}_{model.table_name}",
            migration_type=migration_type,
            upgrade_sql=upgrade_sql,
            downgrade_sql=downgrade_sql,
            metadata={"model_name": model.name, "table_name": model.table_name},
        )

    def _generate_migration_manually(
        self,
        model: BusinessModel,
        operation: str,
        revision_id: Optional[str],
    ) -> MigrationFile:
        """Generate migration without using code generator."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        revision = revision_id or timestamp

        if operation == "create":
            upgrade_sql = self._generate_create_table_sql(model)
            downgrade_sql = self._generate_drop_table_sql(model)
            migration_type = MigrationType.CREATE_TABLE
        elif operation == "drop":
            upgrade_sql = self._generate_drop_table_sql(model)
            downgrade_sql = self._generate_create_table_sql(model)
            migration_type = MigrationType.DROP_TABLE
        else:
            upgrade_sql = "-- TODO: Implement alter table migration"
            downgrade_sql = "-- TODO: Implement alter table rollback"
            migration_type = MigrationType.ALTER_TABLE

        return MigrationFile(
            revision_id=revision,
            name=f"{operation}_{model.table_name}",
            migration_type=migration_type,
            upgrade_sql=upgrade_sql,
            downgrade_sql=downgrade_sql,
            metadata={"model_name": model.name, "table_name": model.table_name},
        )

    def _generate_create_table_sql(self, model: BusinessModel) -> str:
        """Generate CREATE TABLE SQL for a model."""
        columns = []

        for field in model.fields:
            col_def = self._field_to_sql_column(field)
            columns.append(f"    {col_def}")

        columns_str = ",\n".join(columns)

        return f'''CREATE TABLE {model.table_name} (
{columns_str}
);'''

    def _generate_drop_table_sql(self, model: BusinessModel) -> str:
        """Generate DROP TABLE SQL for a model."""
        return f"DROP TABLE IF EXISTS {model.table_name};"

    def _field_to_sql_column(self, field: FieldDefinition) -> str:
        """Convert FieldDefinition to SQL column definition."""
        sql_type = self._get_sql_type(field)
        parts = [field.name, sql_type]

        if field.primary_key:
            parts.append("PRIMARY KEY")

        if field.auto_increment:
            parts.append("AUTOINCREMENT")

        if not field.nullable and not field.primary_key:
            parts.append("NOT NULL")

        if field.unique:
            parts.append("UNIQUE")

        if field.default is not None:
            parts.append(f"DEFAULT {self._format_default(field.default)}")

        if field.foreign_key:
            parts.append(f"REFERENCES {field.foreign_key}")

        return " ".join(parts)

    def _get_sql_type(self, field: FieldDefinition) -> str:
        """Get SQL type for a field."""
        type_map = {
            FieldType.STRING: f"VARCHAR(255)",
            FieldType.INTEGER: "INTEGER",
            FieldType.FLOAT: "FLOAT",
            FieldType.BOOLEAN: "BOOLEAN",
            FieldType.DATETIME: "TIMESTAMP",
            FieldType.DATE: "DATE",
            FieldType.TIME: "TIME",
            FieldType.UUID: "UUID",
            FieldType.JSON: "JSONB",
            FieldType.BINARY: "BYTEA",
            FieldType.TEXT: "TEXT",
            FieldType.DECIMAL: "DECIMAL(10, 2)",
            FieldType.EMAIL: "VARCHAR(255)",
            FieldType.URL: "VARCHAR(500)",
            FieldType.PHONE: "VARCHAR(20)",
        }

        return type_map.get(field.field_type, "VARCHAR(255)")

    def _format_default(self, default: Any) -> str:
        """Format default value for SQL."""
        if isinstance(default, str):
            return f"'{default}'"
        elif isinstance(default, bool):
            return "TRUE" if default else "FALSE"
        elif default is None:
            return "NULL"
        return str(default)

    def _extract_upgrade_sql(self, content: str) -> str:
        """Extract upgrade SQL from migration file content."""
        # Look for upgrade function body (everything after def upgrade and docstring)
        match = re.search(
            r"def\s+upgrade\s*\([^)]*\)[^:]*:\s*\"\"\"[^\"\"]*\"\"\"\s*(.+?)(?=\ndef\s+downgrade|\Z)",
            content,
            re.DOTALL,
        )
        if match:
            return match.group(1).strip()

        # Look for raw SQL in content
        if "CREATE TABLE" in content:
            start = content.find("CREATE TABLE")
            end = content.find(";", start) + 1
            return content[start:end]

        # Look for op.create_table calls (Alembic style)
        if "op.create_table" in content:
            match = re.search(r"(op\.create_table\([^)]+\))", content, re.DOTALL)
            if match:
                return match.group(1)

        return "-- Upgrade SQL not found"

    def _extract_downgrade_sql(self, content: str) -> str:
        """Extract downgrade SQL from migration file content."""
        # Look for downgrade function body (everything after def downgrade and docstring)
        match = re.search(
            r"def\s+downgrade\s*\([^)]*\)[^:]*:\s*\"\"\"[^\"\"]*\"\"\"\s*(.+?)(?=\ndef\s+\w|\Z)",
            content,
            re.DOTALL,
        )
        if match:
            return match.group(1).strip()

        # Look for DROP TABLE
        if "DROP TABLE" in content:
            start = content.find("DROP TABLE")
            end = content.find(";", start) + 1
            return content[start:end]

        # Look for op.drop_table calls (Alembic style)
        if "op.drop_table" in content:
            match = re.search(r"(op\.drop_table\([^)]+\))", content, re.DOTALL)
            if match:
                return match.group(1)

        return "-- Downgrade SQL not found"

    # -----------------------------------------------------------------------
    # Data Validation
    # -----------------------------------------------------------------------

    async def validate_data_changes(
        self,
        changes: Dict[str, Any],
        existing_data: Optional[Dict[str, Any]] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """Validate proposed data changes.

        Args:
            changes: Proposed changes to validate
            existing_data: Current data state
            constraints: Constraints to check against

        Returns:
            ValidationResult with validation outcome
        """
        existing_data = existing_data or {}
        constraints = constraints or {}

        prompt = format_data_validation_prompt(
            changes=json.dumps(changes, ensure_ascii=False, indent=2),
            existing_data=json.dumps(existing_data, ensure_ascii=False, indent=2),
            constraints=json.dumps(constraints, ensure_ascii=False, indent=2),
        )

        messages = [
            ChatMessage(role="system", content=get_system_prompt()),
            ChatMessage(role="user", content=prompt),
        ]

        response = await self.llm.chat(messages, temperature=0.3)
        return self._parse_validation_result(response.content)

    def _parse_validation_result(self, content: str) -> ValidationResult:
        """Parse LLM response into ValidationResult."""
        result = ValidationResult(is_valid=True)

        lines = content.split("\n")
        for line in lines:
            line_lower = line.lower()

            if "error" in line_lower and ("found" in line_lower or "issue" in line_lower):
                if line.strip().startswith("-") or line.strip().startswith("*"):
                    result.errors.append(line.strip("- *").strip())
                result.is_valid = False

            if "warning" in line_lower:
                if line.strip().startswith("-") or line.strip().startswith("*"):
                    result.warnings.append(line.strip("- *").strip())

            if "integrity" in line_lower and "issue" in line_lower:
                result.data_integrity_issues.append(line.strip("- *").strip())

        return result

    # -----------------------------------------------------------------------
    # Migration Review
    # -----------------------------------------------------------------------

    async def review_migration(
        self,
        migration: MigrationFile,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Review a migration for safety and best practices.

        Args:
            migration: Migration to review
            context: Additional context for review

        Returns:
            Review result with approval status and recommendations
        """
        context = context or {}

        prompt = format_migration_review_prompt(
            migration=f"{migration.upgrade_sql}\n\n-- Downgrade:\n{migration.downgrade_sql}",
            context=json.dumps(context, ensure_ascii=False, indent=2),
        )

        messages = [
            ChatMessage(role="system", content=get_system_prompt()),
            ChatMessage(role="user", content=prompt),
        ]

        response = await self.llm.chat(messages, temperature=0.3)

        return self._parse_migration_review(response.content, migration)

    def _parse_migration_review(
        self,
        content: str,
        migration: MigrationFile,
    ) -> Dict[str, Any]:
        """Parse migration review result."""
        result = {
            "approved": True,
            "migration_id": migration.revision_id,
            "recommendations": [],
            "warnings": [],
            "estimated_time": "Unknown",
        }

        content_lower = content.lower()

        # Check for approval
        if "reject" in content_lower or "unsafe" in content_lower:
            result["approved"] = False

        # Extract recommendations
        lines = content.split("\n")
        for line in lines:
            if line.strip().startswith("-") or line.strip().startswith("*"):
                stripped = line.strip("- *").strip()
                if stripped:
                    result["recommendations"].append(stripped)

        # Estimate execution time based on migration type
        if migration.migration_type == MigrationType.CREATE_TABLE:
            result["estimated_time"] = "< 1 second"
        elif migration.migration_type == MigrationType.ADD_INDEX:
            result["estimated_time"] = "1-10 seconds (depends on data size)"
        elif migration.migration_type == MigrationType.ALTER_TABLE:
            result["estimated_time"] = "1-30 seconds (may require table lock)"

        return result

    # -----------------------------------------------------------------------
    # Schema Change Processing
    # -----------------------------------------------------------------------

    async def process_model_change(
        self,
        change: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> DataChangeResult:
        """Process a model change request.

        Args:
            change: Model change specification
            context: Additional context

        Returns:
            DataChangeResult with migration and validation
        """
        context = context or {}
        change_type = change.get("type", "unknown")

        try:
            # Determine impact
            impact = self._assess_impact(change)

            # Generate migration if model is provided
            migration = None
            if "model" in change:
                model = change["model"]
                if isinstance(model, dict):
                    model = self._dict_to_model(model)

                operation = change.get("operation", "create")
                migration = await self.generate_migration(model, operation)

            # Validate changes
            validation = await self.validate_data_changes(
                changes=change,
                existing_data=context.get("existing_data"),
                constraints=context.get("constraints"),
            )

            # Generate recommendations
            recommendations = self._generate_change_recommendations(
                change, impact, validation
            )

            return DataChangeResult(
                success=validation.is_valid,
                migration=migration,
                validation=validation,
                impact=impact,
                summary=self._generate_change_summary(change, validation),
                recommendations=recommendations,
            )

        except Exception as e:
            logger.error(f"Error processing model change: {e}")
            return DataChangeResult(
                success=False,
                summary=f"处理模型变更时出错：{str(e)}",
                impact=SchemaChangeImpact.HIGH,
            )

    def _assess_impact(self, change: Dict[str, Any]) -> SchemaChangeImpact:
        """Assess the impact of a schema change."""
        change_type = change.get("type", "").lower()
        operation = change.get("operation", "").lower()

        # Breaking changes
        if operation in ("drop", "delete"):
            if change_type in ("table", "model"):
                return SchemaChangeImpact.BREAKING
            return SchemaChangeImpact.HIGH

        # High impact changes
        if operation in ("alter", "modify"):
            if any(
                field.get("nullable") == False
                for field in change.get("fields", [])
            ):
                return SchemaChangeImpact.HIGH
            return SchemaChangeImpact.MEDIUM

        # Low impact changes
        if operation in ("create", "add"):
            return SchemaChangeImpact.LOW

        return SchemaChangeImpact.NONE

    def _dict_to_model(self, data: Dict[str, Any]) -> BusinessModel:
        """Convert dictionary to BusinessModel."""
        fields = []
        for field_data in data.get("fields", []):
            field_type_str = field_data.get("type", "string").upper()
            try:
                field_type = FieldType[field_type_str]
            except KeyError:
                field_type = FieldType.STRING

            fields.append(FieldDefinition(
                name=field_data.get("name", "unknown"),
                field_type=field_type,
                required=field_data.get("required", True),
                nullable=field_data.get("nullable", False),
                primary_key=field_data.get("primary_key", False),
                unique=field_data.get("unique", False),
                default=field_data.get("default"),
            ))

        return BusinessModel(
            name=data.get("name", "UnknownModel"),
            table_name=data.get("table_name", "unknown_table"),
            description=data.get("description", ""),
            fields=fields,
        )

    def _generate_change_recommendations(
        self,
        change: Dict[str, Any],
        impact: SchemaChangeImpact,
        validation: ValidationResult,
    ) -> List[str]:
        """Generate recommendations for a schema change."""
        recommendations = []

        if impact == SchemaChangeImpact.BREAKING:
            recommendations.append("此变更可能导致应用程序崩溃，请确保所有依赖方已更新")
            recommendations.append("建议在低峰期执行此变更")

        if impact == SchemaChangeImpact.HIGH:
            recommendations.append("此变更可能需要表锁定，建议在维护窗口执行")

        if validation.warnings:
            recommendations.append(f"验证警告: {'; '.join(validation.warnings[:3])}")

        if validation.data_integrity_issues:
            recommendations.append(
                f"数据完整性问题: {'; '.join(validation.data_integrity_issues[:3])}"
            )

        if not recommendations:
            recommendations.append("变更已通过验证，可以安全执行")

        return recommendations

    def _generate_change_summary(
        self,
        change: Dict[str, Any],
        validation: ValidationResult,
    ) -> str:
        """Generate summary for a schema change."""
        operation = change.get("operation", "unknown")
        model_name = change.get("name", change.get("model", {}).get("name", "unknown"))

        status = "成功" if validation.is_valid else "失败"
        summary = f"模型 '{model_name}' {operation} 操作{status}"

        if validation.errors:
            summary += f"，发现 {len(validation.errors)} 个错误"

        return summary

    # -----------------------------------------------------------------------
    # Request Handlers
    # -----------------------------------------------------------------------

    def _detect_operation_type(self, message: str) -> str:
        """Detect the type of operation from message."""
        message_lower = message.lower()

        if any(kw in message_lower for kw in ["design", "create schema", "new table"]):
            return "schema_design"

        if any(kw in message_lower for kw in ["migrate", "migration", "alter table"]):
            return "migration"

        if any(kw in message_lower for kw in ["validate", "check", "verify"]):
            return "validation"

        if any(kw in message_lower for kw in ["optimize", "performance", "slow query"]):
            return "optimization"

        return "schema_change"

    async def _handle_schema_design(
        self,
        message: str,
        context: Dict[str, Any],
    ) -> SchemaAnalysis:
        """Handle schema design request."""
        return await self.design_schema(message, context)

    async def _handle_migration_request(
        self,
        message: str,
        context: Dict[str, Any],
    ) -> DataChangeResult:
        """Handle migration request."""
        # Try to extract model from context
        model = context.get("model")
        operation = context.get("operation", "create")

        if model:
            if isinstance(model, dict):
                model = self._dict_to_model(model)

            migration = await self.generate_migration(model, operation)

            return DataChangeResult(
                success=True,
                migration=migration,
                impact=self._assess_impact({"operation": operation}),
                summary=f"已生成 {operation} 迁移: {migration.revision_id}",
            )

        return DataChangeResult(
            success=False,
            summary="未找到模型定义，无法生成迁移",
        )

    async def _handle_validation_request(
        self,
        message: str,
        context: Dict[str, Any],
    ) -> ValidationResult:
        """Handle validation request."""
        changes = context.get("changes", {"description": message})
        existing_data = context.get("existing_data")
        constraints = context.get("constraints")

        return await self.validate_data_changes(
            changes=changes,
            existing_data=existing_data,
            constraints=constraints,
        )

    async def _handle_optimization_request(
        self,
        message: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle optimization request."""
        query = context.get("query", message)
        performance = context.get("performance", "Unknown")

        prompt = format_query_optimization_prompt(
            query=query,
            performance=performance,
        )

        messages = [
            ChatMessage(role="system", content=get_system_prompt()),
            ChatMessage(role="user", content=prompt),
        ]

        response = await self.llm.chat(messages, temperature=0.3)

        return {
            "optimization_analysis": response.content,
            "query": query,
        }

    async def _handle_schema_change(
        self,
        message: str,
        context: Dict[str, Any],
    ) -> DataChangeResult:
        """Handle general schema change request."""
        change = {
            "type": "model",
            "operation": "create",
            "description": message,
            **context,
        }

        return await self.process_model_change(change, context)

    # -----------------------------------------------------------------------
    # Helper Methods
    # -----------------------------------------------------------------------

    def _format_response(self, result: Any) -> str:
        """Format result for display."""
        if isinstance(result, SchemaAnalysis):
            return self._format_schema_analysis(result)
        elif isinstance(result, DataChangeResult):
            return self._format_data_change_result(result)
        elif isinstance(result, ValidationResult):
            return self._format_validation_result(result)
        elif isinstance(result, dict):
            return self._format_dict_result(result)
        return str(result)

    def _format_schema_analysis(self, analysis: SchemaAnalysis) -> str:
        """Format schema analysis for display."""
        lines = ["## Schema 分析结果", ""]

        if analysis.table_definitions:
            lines.append("### 表定义")
            for table in analysis.table_definitions:
                lines.append(f"- **{table.name}** ({len(table.columns)} 列)")
            lines.append("")

        if analysis.recommendations:
            lines.append("### 建议")
            for rec in analysis.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        return "\n".join(lines)

    def _format_data_change_result(self, result: DataChangeResult) -> str:
        """Format data change result for display."""
        lines = [f"## 数据变更结果: {'成功' if result.success else '失败'}", ""]
        lines.append(f"**影响级别**: {result.impact.value}")
        lines.append(f"**摘要**: {result.summary}")
        lines.append("")

        if result.migration:
            lines.append("### 生成的迁移")
            lines.append(f"- Revision: {result.migration.revision_id}")
            lines.append(f"- 类型: {result.migration.migration_type.value}")
            lines.append("")

        if result.recommendations:
            lines.append("### 建议")
            for rec in result.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        return "\n".join(lines)

    def _format_validation_result(self, result: ValidationResult) -> str:
        """Format validation result for display."""
        status = "通过" if result.is_valid else "失败"
        lines = [f"## 验证结果: {status}", ""]

        if result.errors:
            lines.append("### 错误")
            for err in result.errors:
                lines.append(f"- {err}")
            lines.append("")

        if result.warnings:
            lines.append("### 警告")
            for warn in result.warnings:
                lines.append(f"- {warn}")
            lines.append("")

        return "\n".join(lines)

    def _format_dict_result(self, result: Dict[str, Any]) -> str:
        """Format dictionary result for display."""
        lines = ["## 结果", ""]
        for key, value in result.items():
            if isinstance(value, str) and len(value) > 200:
                value = value[:200] + "..."
            lines.append(f"- **{key}**: {value}")
        return "\n".join(lines)

    def _summarize_results(self, results: List[DataChangeResult]) -> str:
        """Summarize multiple results."""
        success_count = sum(1 for r in results if r.success)
        total = len(results)

        summary = f"处理完成: {success_count}/{total} 成功\n\n"

        for i, result in enumerate(results, 1):
            summary += f"{i}. {result.summary}\n"

        return summary

    def clear_session(self, session_id: str) -> bool:
        """Clear a session from memory.

        Args:
            session_id: Session identifier

        Returns:
            True if session was cleared
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False