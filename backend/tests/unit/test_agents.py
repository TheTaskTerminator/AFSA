"""Tests for Agent layer - LLM providers, adapters, and agents."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import json

from app.agents.base import AgentResponse, AgentType, BaseAgent, TaskCard
from app.agents.llm import (
    BaseLLM,
    ChatMessage,
    LLMConfig,
    LLMProvider,
    get_llm,
)
from app.agents.adapters.base import FrameworkAdapter, get_adapter
from app.agents.pm_agent import PMAgent, ConversationState
from app.agents.frontend_agent import FrontendAgent, GenerationSession
from app.agents.frontend_agent.prompts import detect_component_type
from app.agents.backend_agent import BackendAgent, BackendSession
from app.agents.tools import (
    BaseTool,
    ToolResult,
    FileReadTool,
    FileWriteTool,
    CodeAnalysisTool,
    CodeFormatTool,
)


# ============== LLM Provider Tests ==============

class TestLLMConfig:
    """Tests for LLM configuration."""

    def test_llm_config_defaults(self):
        """Test LLM config default values."""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key="test-key",
            model="gpt-4",
        )
        assert config.provider == LLMProvider.OPENAI
        assert config.temperature == 0.7
        assert config.max_tokens == 4096

    def test_llm_config_custom_values(self):
        """Test LLM config with custom values."""
        config = LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            api_key="test-key",
            model="claude-3-opus-20240229",
            temperature=0.5,
            max_tokens=2048,
        )
        assert config.provider == LLMProvider.ANTHROPIC
        assert config.model == "claude-3-opus-20240229"
        assert config.temperature == 0.5
        assert config.max_tokens == 2048

    def test_llm_provider_enum(self):
        """Test LLM provider enum values."""
        assert LLMProvider.OPENAI.value == "openai"
        assert LLMProvider.ANTHROPIC.value == "anthropic"
        assert LLMProvider.VOLCENGINE.value == "volcengine"
        assert LLMProvider.ALIYUN.value == "aliyun"
        assert LLMProvider.GLM.value == "glm"


class TestChatMessage:
    """Tests for ChatMessage."""

    def test_chat_message_creation(self):
        """Test chat message creation."""
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_chat_message_with_name(self):
        """Test chat message with name."""
        msg = ChatMessage(role="system", content="You are helpful.", name="assistant")
        assert msg.role == "system"
        assert msg.content == "You are helpful."
        assert msg.name == "assistant"


class TestBaseLLM:
    """Tests for BaseLLM abstract class."""

    def test_base_llm_is_abstract(self):
        """Test that BaseLLM cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseLLM(config=LLMConfig(provider=LLMProvider.OPENAI, api_key="test"))


# ============== Agent Base Tests ==============

class TestTaskCard:
    """Tests for TaskCard."""

    def test_task_card_creation(self):
        """Test task card creation."""
        card = TaskCard(
            id="test-id",
            type="feature",
            priority="high",
            description="Implement login",
            structured_requirements=[],
            constraints={},
        )
        assert card.id == "test-id"
        assert card.type == "feature"
        assert card.priority == "high"
        assert card.description == "Implement login"

    def test_task_card_with_requirements(self):
        """Test task card with structured requirements."""
        card = TaskCard(
            id="test-id",
            type="feature",
            priority="medium",
            description="Add user management",
            structured_requirements=[
                {"id": "req-1", "description": "Create user", "acceptance_criteria": "User created"},
                {"id": "req-2", "description": "Delete user", "acceptance_criteria": "User deleted"},
            ],
            constraints={"tech_stack": ["Python", "FastAPI"]},
        )
        assert len(card.structured_requirements) == 2
        assert card.structured_requirements[0]["id"] == "req-1"


class TestAgentResponse:
    """Tests for AgentResponse."""

    def test_agent_response_success(self):
        """Test successful agent response."""
        response = AgentResponse(
            success=True,
            content="Task completed",
        )
        assert response.success is True
        assert response.content == "Task completed"
        assert response.metadata is None

    def test_agent_response_with_metadata(self):
        """Test agent response with metadata."""
        response = AgentResponse(
            success=False,
            content="",
            metadata={"error": "Something went wrong"},
        )
        assert response.success is False
        assert response.metadata["error"] == "Something went wrong"


# ============== PM Agent Tests ==============

class TestConversationState:
    """Tests for ConversationState."""

    def test_conversation_state_creation(self):
        """Test conversation state creation."""
        state = ConversationState(session_id="session-123")
        assert state.session_id == "session-123"
        assert len(state.messages) == 0
        assert state.is_complete is False

    def test_conversation_state_add_message(self):
        """Test adding messages to conversation state."""
        state = ConversationState(session_id="session-123")
        state.messages.append({
            "role": "user",
            "content": "Hello",
            "timestamp": datetime.utcnow().isoformat(),
        })
        assert len(state.messages) == 1
        assert state.messages[0]["role"] == "user"


class TestPMAgent:
    """Tests for PM Agent."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM."""
        llm = MagicMock(spec=BaseLLM)
        llm.chat = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "type": "clarification",
                "questions": ["What type of API do you need?"]
            })
        ))
        return llm

    @pytest.fixture
    def pm_agent(self, mock_llm):
        """Create a PM Agent with mock LLM."""
        return PMAgent(llm=mock_llm)

    @pytest.mark.asyncio
    async def test_pm_agent_process_message(self, pm_agent):
        """Test PM Agent processing a message."""
        response = await pm_agent.process_message(
            session_id="test-session",
            message="I need a user management API",
        )
        assert response.success is True
        assert response.metadata["session_id"] == "test-session"

    @pytest.mark.asyncio
    async def test_pm_agent_generate_task_card(self, pm_agent):
        """Test PM Agent generating a task card."""
        # First process a message to create session
        await pm_agent.process_message(
            session_id="test-session",
            message="Create a login feature",
        )

        # Generate task card
        task_card = await pm_agent.generate_task_card("test-session")
        assert task_card is not None
        assert task_card.type == "feature"

    @pytest.mark.asyncio
    async def test_pm_agent_clear_session(self, pm_agent):
        """Test clearing PM Agent session."""
        await pm_agent.process_message(
            session_id="test-session",
            message="Test message",
        )
        result = pm_agent.clear_session("test-session")
        assert result is True


# ============== Frontend Agent Tests ==============

class TestGenerationSession:
    """Tests for GenerationSession."""

    def test_generation_session_creation(self):
        """Test generation session creation."""
        session = GenerationSession(session_id="session-456")
        assert session.session_id == "session-456"
        assert len(session.generated_files) == 0

    def test_generation_session_add_file(self):
        """Test adding files to generation session."""
        session = GenerationSession(session_id="session-456")
        from app.agents.frontend_agent.tools import GeneratedFile
        session.generated_files.append(
            GeneratedFile(
                path="src/components/Button.tsx",
                content="export const Button = () => {}",
                language="typescript",
            )
        )
        assert len(session.generated_files) == 1


class TestFrontendAgent:
    """Tests for Frontend Agent."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM."""
        llm = MagicMock(spec=BaseLLM)
        llm.chat = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "type": "code_generation",
                "files": [{
                    "path": "src/components/Test.tsx",
                    "content": "export const Test = () => <div/>",
                    "language": "typescript",
                }]
            })
        ))
        return llm

    @pytest.fixture
    def frontend_agent(self, mock_llm):
        """Create a Frontend Agent with mock LLM."""
        return FrontendAgent(llm=mock_llm)

    @pytest.mark.asyncio
    async def test_frontend_agent_process_message(self, frontend_agent):
        """Test Frontend Agent processing a message."""
        response = await frontend_agent.process_message(
            session_id="test-session",
            message="Create a login form",
        )
        assert response.success is True

    @pytest.mark.asyncio
    async def test_frontend_agent_detect_component_type(self, frontend_agent):
        """Test detecting component type."""
        # detect_component_type is a function in prompts module
        assert detect_component_type("Create a login form") == "form"
        assert detect_component_type("Build a user list") == "list"
        assert detect_component_type("Dashboard page") == "page"


# ============== Backend Agent Tests ==============

class TestBackendSession:
    """Tests for BackendSession."""

    def test_backend_session_creation(self):
        """Test backend session creation."""
        session = BackendSession(session_id="session-789")
        assert session.session_id == "session-789"
        assert len(session.generated_files) == 0


class TestBackendAgent:
    """Tests for Backend Agent."""

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM."""
        llm = MagicMock(spec=BaseLLM)
        llm.chat = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "type": "code_generation",
                "files": [{
                    "path": "app/api/v1/users.py",
                    "content": "from fastapi import APIRouter\nrouter = APIRouter()",
                    "language": "python",
                }]
            })
        ))
        return llm

    @pytest.fixture
    def backend_agent(self, mock_llm):
        """Create a Backend Agent with mock LLM."""
        return BackendAgent(llm=mock_llm)

    @pytest.mark.asyncio
    async def test_backend_agent_process_message(self, backend_agent):
        """Test Backend Agent processing a message."""
        response = await backend_agent.process_message(
            session_id="test-session",
            message="Create a user CRUD API",
        )
        assert response.success is True

    @pytest.mark.asyncio
    async def test_backend_agent_detect_file_type(self, backend_agent):
        """Test detecting file type."""
        assert backend_agent._detect_file_type("app/api/v1/users.py") == "api"
        assert backend_agent._detect_file_type("app/models/user.py") == "model"
        assert backend_agent._detect_file_type("app/schemas/user.py") == "schema"


# ============== Tool Tests ==============

class TestBaseTool:
    """Tests for BaseTool."""

    def test_tool_validate_parameters_success(self):
        """Test parameter validation with valid params."""
        tool = FileReadTool()
        error = tool.validate_parameters(path="/test/file.txt")
        assert error is None

    def test_tool_validate_parameters_missing(self):
        """Test parameter validation with missing required param."""
        tool = FileReadTool()
        error = tool.validate_parameters()
        assert error is not None
        assert "Missing required parameters" in error

    def test_tool_to_openai_schema(self):
        """Test converting tool to OpenAI schema."""
        tool = FileReadTool()
        schema = tool.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "file_read"
        assert "path" in schema["function"]["parameters"]["properties"]


class TestFileReadTool:
    """Tests for FileReadTool."""

    @pytest.fixture
    def file_read_tool(self):
        """Create a FileReadTool."""
        return FileReadTool()

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(self, file_read_tool, tmp_path):
        """Test reading a nonexistent file."""
        result = await file_read_tool.execute(
            path=str(tmp_path / "nonexistent.txt")
        )
        assert result.success is False
        assert "不存在" in result.error

    @pytest.mark.asyncio
    async def test_read_existing_file(self, file_read_tool, tmp_path):
        """Test reading an existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        result = await file_read_tool.execute(path=str(test_file))
        assert result.success is True
        assert "Hello, World!" in result.output


class TestFileWriteTool:
    """Tests for FileWriteTool."""

    @pytest.fixture
    def file_write_tool(self):
        """Create a FileWriteTool."""
        return FileWriteTool()

    @pytest.mark.asyncio
    async def test_write_new_file(self, file_write_tool, tmp_path):
        """Test writing a new file."""
        test_file = tmp_path / "new_file.txt"

        result = await file_write_tool.execute(
            path=str(test_file),
            content="New content",
        )
        assert result.success is True
        assert test_file.read_text() == "New content"

    @pytest.mark.asyncio
    async def test_write_creates_directories(self, file_write_tool, tmp_path):
        """Test writing creates parent directories."""
        test_file = tmp_path / "subdir" / "nested" / "file.txt"

        result = await file_write_tool.execute(
            path=str(test_file),
            content="Nested content",
            create_dirs=True,
        )
        assert result.success is True
        assert test_file.exists()


class TestCodeAnalysisTool:
    """Tests for CodeAnalysisTool."""

    @pytest.fixture
    def code_analysis_tool(self):
        """Create a CodeAnalysisTool."""
        return CodeAnalysisTool()

    @pytest.mark.asyncio
    async def test_analyze_valid_code(self, code_analysis_tool):
        """Test analyzing valid Python code."""
        code = '''
def hello():
    """Say hello."""
    return "Hello, World!"
'''
        result = await code_analysis_tool.execute(code=code)
        assert result.success is True
        assert "metrics" in result.output

    @pytest.mark.asyncio
    async def test_analyze_invalid_code(self, code_analysis_tool):
        """Test analyzing invalid Python code."""
        code = "def broken(:"
        result = await code_analysis_tool.execute(code=code)
        assert result.success is False
        assert "语法错误" in result.error


class TestCodeFormatTool:
    """Tests for CodeFormatTool."""

    @pytest.fixture
    def code_format_tool(self):
        """Create a CodeFormatTool."""
        return CodeFormatTool()

    @pytest.mark.asyncio
    async def test_format_basic(self, code_format_tool):
        """Test basic code formatting."""
        code = "def hello():\n    return 'hello'  "
        result = await code_format_tool.execute(
            code=code,
            formatter="basic",
        )
        assert result.success is True
        assert result.output.strip() == code.strip()


# ============== Adapter Tests ==============

class TestFrameworkAdapter:
    """Tests for FrameworkAdapter."""

    def test_create_langgraph_adapter(self):
        """Test creating LangGraph adapter."""
        adapter = get_adapter("langgraph")
        assert adapter is not None
        assert isinstance(adapter, FrameworkAdapter)

    def test_create_unsupported_adapter(self):
        """Test creating unsupported adapter returns default."""
        adapter = get_adapter("unsupported")
        # Should return default LangGraphAdapter
        assert adapter is not None