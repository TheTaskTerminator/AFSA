"""Unit tests for Backend Agent."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.backend_agent import (
    BackendAgent,
    BackendSession,
    APIGenerationTool,
    SchemaGenerationTool,
    CodeReviewTool,
    GeneratedFile,
    APIGenerationResult,
    APISpec,
    ModelDefinition,
)
from app.agents.base import AgentResponse, AgentType, TaskCard


# ---------------------------------------------------------------------------
# GeneratedFile Tests
# ---------------------------------------------------------------------------

class TestGeneratedFile:
    """Tests for GeneratedFile."""

    def test_create_file(self):
        """Test creating a generated file."""
        file = GeneratedFile(
            path="app/api/v1/users.py",
            content="from fastapi import APIRouter",
            description="Users API",
            language="python",
        )
        assert file.path == "app/api/v1/users.py"
        assert "fastapi" in file.content
        assert file.language == "python"

    def test_file_default_language(self):
        """Test default language is python."""
        file = GeneratedFile(
            path="app/models/user.py",
            content="class User(Base): pass",
        )
        assert file.language == "python"


# ---------------------------------------------------------------------------
# APIGenerationResult Tests
# ---------------------------------------------------------------------------

class TestAPIGenerationResult:
    """Tests for APIGenerationResult."""

    def test_create_result(self):
        """Test creating API generation result."""
        result = APIGenerationResult(
            files=[
                GeneratedFile(path="app/api/v1/users.py", content="# Users API"),
            ],
            dependencies=["fastapi", "sqlalchemy"],
            migrations=["001_create_users.sql"],
        )
        assert len(result.files) == 1
        assert len(result.dependencies) == 2
        assert len(result.migrations) == 1

    def test_result_with_errors(self):
        """Test result with errors."""
        result = APIGenerationResult(
            files=[],
            errors=["Failed to generate API"],
        )
        assert len(result.files) == 0
        assert len(result.errors) == 1


# ---------------------------------------------------------------------------
# ModelDefinition Tests
# ---------------------------------------------------------------------------

class TestModelDefinition:
    """Tests for ModelDefinition."""

    def test_create_model(self):
        """Test creating a model definition."""
        model = ModelDefinition(
            name="User",
            table_name="users",
            fields=[
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        )
        assert model.name == "User"
        assert model.table_name == "users"
        assert len(model.fields) == 2

    def test_model_with_relationships(self):
        """Test model with relationships."""
        model = ModelDefinition(
            name="Post",
            table_name="posts",
            fields=[{"name": "id", "type": "integer"}],
            relationships=[
                {"type": "many_to_one", "target": "User"},
            ],
        )
        assert len(model.relationships) == 1


# ---------------------------------------------------------------------------
# APISpec Tests
# ---------------------------------------------------------------------------

class TestAPISpec:
    """Tests for APISpec."""

    def test_create_spec(self):
        """Test creating API spec."""
        spec = APISpec(
            path="/api/v1/users",
            method="GET",
            description="List users",
            auth_required=True,
        )
        assert spec.path == "/api/v1/users"
        assert spec.method == "GET"
        assert spec.auth_required is True

    def test_spec_optional_fields(self):
        """Test spec with optional fields."""
        spec = APISpec(
            path="/api/v1/users",
            method="POST",
            description="Create user",
            request_schema="UserCreate",
            response_schema="UserResponse",
        )
        assert spec.request_schema == "UserCreate"
        assert spec.response_schema == "UserResponse"


# ---------------------------------------------------------------------------
# BackendSession Tests
# ---------------------------------------------------------------------------

class TestBackendSession:
    """Tests for BackendSession."""

    def test_create_session(self):
        """Test creating a backend session."""
        session = BackendSession(session_id="test-session")
        assert session.session_id == "test-session"
        assert len(session.messages) == 0
        assert len(session.generated_files) == 0
        assert session.is_complete is False

    def test_session_with_files(self):
        """Test session with generated files."""
        session = BackendSession(session_id="session-1")
        session.generated_files.append(
            GeneratedFile(path="app/api/v1/users.py", content="# Users API")
        )
        assert len(session.generated_files) == 1


# ---------------------------------------------------------------------------
# BackendAgent Tests
# ---------------------------------------------------------------------------

class TestBackendAgent:
    """Tests for BackendAgent class."""

    @pytest.fixture
    def agent(self):
        """Create BackendAgent instance."""
        return BackendAgent()

    def test_agent_type(self, agent):
        """Test agent type."""
        assert agent.agent_type == AgentType.BACKEND
        assert agent.name == "Backend Agent"

    def test_get_or_create_session(self, agent):
        """Test session creation."""
        session = agent._get_or_create_session("test-session")
        assert session.session_id == "test-session"
        assert isinstance(session, BackendSession)

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

    def test_parse_response_json_block(self, agent):
        """Test parsing response with JSON block."""
        content = '''
        Some text
        ```json
        {"type": "code_generation", "files": []}
        ```
        '''
        parsed = agent._parse_response(content)
        assert parsed["type"] == "code_generation"

    def test_parse_response_direct_json(self, agent):
        """Test parsing direct JSON response."""
        content = '{"type": "code_generation", "files": []}'
        parsed = agent._parse_response(content)
        assert parsed["type"] == "code_generation"

    def test_parse_response_plain_text(self, agent):
        """Test parsing plain text response."""
        content = "Plain text response"
        parsed = agent._parse_response(content)
        assert parsed["type"] == "response"

    def test_detect_file_type_api(self, agent):
        """Test detecting API file type."""
        file_type = agent._detect_file_type("app/api/v1/users.py")
        assert file_type == "api"

    def test_detect_file_type_model(self, agent):
        """Test detecting model file type."""
        file_type = agent._detect_file_type("app/models/user.py")
        assert file_type == "model"

    def test_detect_file_type_schema(self, agent):
        """Test detecting schema file type."""
        file_type = agent._detect_file_type("app/schemas/user.py")
        assert file_type == "schema"

    def test_detect_file_type_repository(self, agent):
        """Test detecting repository file type."""
        file_type = agent._detect_file_type("app/repositories/user.py")
        assert file_type == "repository"

    def test_detect_file_type_default(self, agent):
        """Test default file type."""
        file_type = agent._detect_file_type("app/utils/helper.py")
        assert file_type == "python"

    def test_get_generated_files_empty(self, agent):
        """Test getting generated files for empty session."""
        files = agent.get_generated_files("nonexistent")
        assert len(files) == 0

    def test_get_generated_files(self, agent):
        """Test getting generated files."""
        session = agent._get_or_create_session("files-test")
        session.generated_files.append(
            GeneratedFile(path="app/api/v1/users.py", content="# Users API")
        )
        
        files = agent.get_generated_files("files-test")
        assert len(files) == 1
        assert files[0].path == "app/api/v1/users.py"


# ---------------------------------------------------------------------------
# BackendAgent API Detection Tests
# ---------------------------------------------------------------------------

class TestBackendAgentAPIDetection:
    """Tests for API type detection."""

    @pytest.fixture
    def agent(self):
        """Create BackendAgent instance."""
        return BackendAgent()

    def test_detect_crud_api(self, agent):
        """Test detecting CRUD API type."""
        from app.agents.backend_agent.prompts import detect_api_type
        
        api_type = detect_api_type("I need CRUD operations for users")
        assert api_type == "crud"

    def test_detect_auth_api(self, agent):
        """Test detecting auth API type."""
        from app.agents.backend_agent.prompts import detect_api_type
        
        api_type = detect_api_type("Implement login authentication")
        assert api_type == "auth"

    def test_detect_search_api(self, agent):
        """Test detecting search API type."""
        from app.agents.backend_agent.prompts import detect_api_type
        
        api_type = detect_api_type("Add search functionality")
        assert api_type == "search"

    def test_extract_model_name_english(self, agent):
        """Test extracting model name from English."""
        from app.agents.backend_agent.prompts import extract_model_name
        
        name = extract_model_name("Create User model")
        assert "User" in name or "Model" in name

    def test_extract_model_name_default(self, agent):
        """Test extracting model name generates default."""
        from app.agents.backend_agent.prompts import extract_model_name
        
        name = extract_model_name("创建一个数据模型")
        assert len(name) > 0


# ---------------------------------------------------------------------------
# BackendAgent Integration Tests with Mocked LLM
# ---------------------------------------------------------------------------

class TestBackendAgentWithMockedLLM:
    """Tests with mocked LLM."""

    @pytest.fixture
    def agent_with_mocked_llm(self):
        """Create BackendAgent with mocked LLM."""
        agent = BackendAgent()
        mock_llm = MagicMock()
        mock_llm.chat = AsyncMock()
        agent._llm = mock_llm
        return agent

    @pytest.mark.asyncio
    async def test_process_message_code_generation(self, agent_with_mocked_llm):
        """Test processing code generation message."""
        agent = agent_with_mocked_llm
        agent.llm.chat.return_value = MagicMock(
            content='''
            ```json
            {
                "type": "code_generation",
                "files": [
                    {
                        "path": "app/api/v1/users.py",
                        "content": "from fastapi import APIRouter",
                        "description": "Users API"
                    }
                ],
                "dependencies": ["fastapi"],
                "migrations": []
            }
            ```
            '''
        )

        response = await agent.process_message(
            session_id="test",
            message="Create users API",
        )

        assert response.success is True
        assert "session_id" in response.metadata
        assert response.metadata["type"] == "code_generation"

    @pytest.mark.asyncio
    async def test_process_message_with_review(self, agent_with_mocked_llm):
        """Test processing message with code review."""
        agent = agent_with_mocked_llm
        agent.llm.chat.return_value = MagicMock(
            content='''
            ```json
            {
                "type": "code_generation",
                "files": [
                    {
                        "path": "app/api/v1/users.py",
                        "content": "from fastapi import APIRouter\\nrouter = APIRouter()",
                        "description": "Users API",
                        "language": "python"
                    }
                ]
            }
            ```
            '''
        )

        response = await agent.process_message(
            session_id="test",
            message="Create API endpoint",
        )

        assert response.success is True

    @pytest.mark.asyncio
    async def test_generate_task_card(self, agent_with_mocked_llm):
        """Test generating task card."""
        agent = agent_with_mocked_llm

        # Create a session with messages
        session = agent._get_or_create_session("task-test")
        session.messages.append({
            "role": "user",
            "content": "Create user management API",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        task_card = await agent.generate_task_card("task-test")
        assert task_card is not None
        assert task_card.type == "feature"

    @pytest.mark.asyncio
    async def test_generate_task_card_empty_session(self, agent_with_mocked_llm):
        """Test generating task card from empty session."""
        agent = agent_with_mocked_llm
        agent._get_or_create_session("empty-session")

        task_card = await agent.generate_task_card("empty-session")
        assert task_card is None

    @pytest.mark.asyncio
    async def test_execute_task_crud(self, agent_with_mocked_llm):
        """Test executing a CRUD task."""
        agent = agent_with_mocked_llm
        
        # Mock the API generation tool
        mock_result = APIGenerationResult(
            files=[
                GeneratedFile(
                    path="app/api/v1/users.py",
                    content="from fastapi import APIRouter",
                ),
            ],
            dependencies=["fastapi"],
        )
        
        with patch.object(APIGenerationTool, 'generate_crud_api', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_result
            
            task_card = TaskCard(
                id="task-1",
                type="feature",
                priority="medium",
                description="Create user CRUD API with fields: name, email",
                requirements=[],
            )

            response = await agent.execute(task_card)
            assert response.success is True
            assert response.content is not None

    @pytest.mark.asyncio
    async def test_execute_task_endpoint(self, agent_with_mocked_llm):
        """Test executing an endpoint generation task."""
        agent = agent_with_mocked_llm
        
        mock_result = APIGenerationResult(
            files=[
                GeneratedFile(
                    path="app/api/v1/endpoint.py",
                    content="@router.get('/test')",
                ),
            ],
        )
        
        with patch.object(APIGenerationTool, 'generate_endpoint', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_result
            
            task_card = TaskCard(
                id="task-2",
                type="feature",
                priority="high",
                description="Add search endpoint for products",
                requirements=[],
            )

            response = await agent.execute(task_card)
            assert response.success is True


# ---------------------------------------------------------------------------
# APIGenerationTool Tests
# ---------------------------------------------------------------------------

class TestAPIGenerationTool:
    """Tests for APIGenerationTool."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM."""
        llm = MagicMock()
        llm.chat = AsyncMock()
        return llm

    @pytest.fixture
    def tool(self, mock_llm):
        """Create APIGenerationTool instance."""
        return APIGenerationTool(mock_llm)

    @pytest.mark.asyncio
    async def test_generate_crud_api(self, tool, mock_llm):
        """Test generating CRUD API."""
        mock_llm.chat.return_value = MagicMock(
            content='''
            ```json
            {
                "files": [
                    {
                        "path": "app/api/v1/users.py",
                        "content": "from fastapi import APIRouter\\nrouter = APIRouter()",
                        "description": "Users CRUD API",
                        "language": "python"
                    }
                ],
                "dependencies": ["fastapi", "sqlalchemy"],
                "migrations": ["001_create_users.sql"]
            }
            ```
            '''
        )

        result = await tool.generate_crud_api(
            model_name="User",
            fields=[
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
            ],
        )

        assert len(result.files) == 1
        assert result.files[0].path == "app/api/v1/users.py"
        assert len(result.dependencies) > 0

    @pytest.mark.asyncio
    async def test_generate_endpoint(self, tool, mock_llm):
        """Test generating single endpoint."""
        mock_llm.chat.return_value = MagicMock(
            content='''
            ```json
            {
                "files": [
                    {
                        "path": "app/api/v1/endpoint.py",
                        "content": "@router.get('/test')",
                        "description": "Test endpoint"
                    }
                ]
            }
            ```
            '''
        )

        result = await tool.generate_endpoint(
            path="/api/v1/test",
            method="GET",
            description="Test endpoint",
        )

        assert len(result.files) == 1

    @pytest.mark.asyncio
    async def test_generate_model(self, tool, mock_llm):
        """Test generating SQLAlchemy model."""
        mock_llm.chat.return_value = MagicMock(
            content='''
            ```json
            {
                "files": [
                    {
                        "path": "app/models/user.py",
                        "content": "class User(Base): pass",
                        "description": "User model"
                    }
                ],
                "migrations": ["CREATE TABLE users"]
            }
            ```
            '''
        )

        result = await tool.generate_model(
            model_name="User",
            fields=[{"name": "id", "type": "integer"}],
        )

        assert len(result.files) == 1
        assert len(result.migrations) > 0

    @pytest.mark.asyncio
    async def test_generate_crud_api_error(self, tool, mock_llm):
        """Test CRUD API generation with error."""
        mock_llm.chat.return_value = MagicMock(
            content="Invalid response"
        )

        result = await tool.generate_crud_api(
            model_name="User",
            fields=[],
        )

        assert len(result.files) == 0
        assert len(result.errors) > 0

    def test_parse_generation_response_json_block(self, tool):
        """Test parsing response with JSON block."""
        content = '''
        ```json
        {
            "files": [{"path": "test.py", "content": "# test"}],
            "dependencies": ["fastapi"]
        }
        ```
        '''
        result = tool._parse_generation_response(content)
        assert len(result.files) == 1

    def test_parse_generation_response_error(self, tool):
        """Test parsing invalid response."""
        content = "Invalid response"
        result = tool._parse_generation_response(content)
        assert len(result.files) == 0
        assert len(result.errors) > 0


# ---------------------------------------------------------------------------
# SchemaGenerationTool Tests
# ---------------------------------------------------------------------------

class TestSchemaGenerationTool:
    """Tests for SchemaGenerationTool."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM."""
        llm = MagicMock()
        llm.chat = AsyncMock()
        return llm

    @pytest.fixture
    def tool(self, mock_llm):
        """Create SchemaGenerationTool instance."""
        return SchemaGenerationTool(mock_llm)

    @pytest.mark.asyncio
    async def test_generate_schema(self, tool, mock_llm):
        """Test generating Pydantic schema."""
        mock_llm.chat.return_value = MagicMock(
            content='''
            ```json
            {
                "files": [
                    {
                        "path": "app/schemas/user.py",
                        "content": "from pydantic import BaseModel",
                        "description": "User schemas"
                    }
                ]
            }
            ```
            '''
        )

        result = await tool.generate_schema(
            name="User",
            fields=[
                {"name": "id", "type": "int"},
                {"name": "name", "type": "str"},
            ],
            include_crud_variants=True,
        )

        assert len(result.files) == 1

    @pytest.mark.asyncio
    async def test_generate_schema_error(self, tool, mock_llm):
        """Test schema generation with error."""
        mock_llm.chat.return_value = MagicMock(
            content="Invalid"
        )

        result = await tool.generate_schema(
            name="Test",
            fields=[],
        )

        assert len(result.files) == 0
        assert len(result.errors) > 0


# ---------------------------------------------------------------------------
# CodeReviewTool Tests
# ---------------------------------------------------------------------------

class TestCodeReviewTool:
    """Tests for CodeReviewTool."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM."""
        llm = MagicMock()
        llm.chat = AsyncMock()
        return llm

    @pytest.fixture
    def tool(self, mock_llm):
        """Create CodeReviewTool instance."""
        return CodeReviewTool(mock_llm)

    @pytest.mark.asyncio
    async def test_review_code_api(self, tool, mock_llm):
        """Test reviewing API code."""
        mock_llm.chat.return_value = MagicMock(
            content='''
            {
                "issues": [],
                "overall_score": 85,
                "summary": "Good code quality"
            }
            '''
        )

        code = """
from fastapi import APIRouter
router = APIRouter()

@router.get("/users")
async def get_users():
    return []
"""

        result = await tool.review_code(code, file_type="api")

        assert "overall_score" in result
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_check_security_sql_injection(self, tool, mock_llm):
        """Test security check for SQL injection."""
        code = """
query = f"SELECT * FROM users WHERE id = {user_id}"
cursor.execute(query)
"""

        result = await tool.check_security(code)

        assert result["has_issues"] is True
        assert any(i["type"] == "sql_injection" for i in result["issues"])

    @pytest.mark.asyncio
    async def test_check_security_hardcoded_credentials(self, tool, mock_llm):
        """Test security check for hardcoded credentials."""
        code = """
password = "secret123"
db_password = "admin"
"""

        result = await tool.check_security(code)

        assert any(i["type"] == "hardcoded_credentials" for i in result["issues"])

    @pytest.mark.asyncio
    async def test_check_security_missing_auth(self, tool, mock_llm):
        """Test security check for missing auth."""
        code = """
@router.post("/admin")
async def admin_action():
    return {"status": "ok"}
"""

        result = await tool.check_security(code)

        # Should warn about missing auth
        assert any(i["type"] == "missing_auth" for i in result["issues"])

    @pytest.mark.asyncio
    async def test_check_security_clean_code(self, tool, mock_llm):
        """Test security check for clean code."""
        code = """
from app.api.deps import get_current_user

@router.get("/users")
async def get_users(current_user = Depends(get_current_user)):
    return []
"""

        result = await tool.check_security(code)

        # Should not have SQL injection issues
        assert not any(i["type"] == "sql_injection" for i in result["issues"])


# ---------------------------------------------------------------------------
# BackendAgent Template Tests
# ---------------------------------------------------------------------------

class TestBackendAgentTemplates:
    """Tests for backend code templates."""

    def test_get_api_template(self):
        """Test getting API template."""
        from app.agents.backend_agent.prompts import get_api_template
        
        template = get_api_template(model="User", model_cn="用户")
        assert "router" in template
        assert "User" in template

    def test_get_model_template(self):
        """Test getting model template."""
        from app.agents.backend_agent.prompts import get_model_template
        
        template = get_model_template(
            model="User",
            fields="id = Column(Integer, primary_key=True)",
            model_cn="用户",
        )
        assert "class User" in template
        assert "__tablename__" in template

    def test_get_schema_template(self):
        """Test getting schema template."""
        from app.agents.backend_agent.prompts import get_schema_template
        
        template = get_schema_template(
            model="User",
            base_fields="id: int",
            update_fields="name: str",
        )
        assert "class User" in template
        assert "pydantic" in template.lower() or "BaseModel" in template
