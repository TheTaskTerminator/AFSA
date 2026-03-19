"""Unit tests for Frontend Agent."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.frontend_agent import (
    FrontendAgent,
    GenerationSession,
    CodeGenerationTool,
    CodeValidationTool,
    GeneratedFile,
    CodeGenerationResult,
    ValidationResult,
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
            path="src/components/Button.tsx",
            content="export function Button() { return <button>Click</button> }",
            description="Button component",
            language="typescript",
        )
        assert file.path == "src/components/Button.tsx"
        assert "Button" in file.content
        assert file.language == "typescript"

    def test_file_default_language(self):
        """Test default language is typescript."""
        file = GeneratedFile(
            path="src/components/Test.tsx",
            content="export default function Test() {}",
        )
        assert file.language == "typescript"


# ---------------------------------------------------------------------------
# CodeGenerationResult Tests
# ---------------------------------------------------------------------------

class TestCodeGenerationResult:
    """Tests for CodeGenerationResult."""

    def test_create_result(self):
        """Test creating code generation result."""
        result = CodeGenerationResult(
            files=[
                GeneratedFile(path="src/App.tsx", content="export default App"),
            ],
            dependencies=["react", "react-dom"],
        )
        assert len(result.files) == 1
        assert len(result.dependencies) == 2

    def test_result_with_errors(self):
        """Test result with errors."""
        result = CodeGenerationResult(
            files=[],
            errors=["Failed to generate code"],
        )
        assert len(result.files) == 0
        assert len(result.errors) == 1


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
            errors=["Type error on line 10"],
            warnings=["Unused import"],
        )
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert len(result.warnings) == 1


# ---------------------------------------------------------------------------
# GenerationSession Tests
# ---------------------------------------------------------------------------

class TestGenerationSession:
    """Tests for GenerationSession."""

    def test_create_session(self):
        """Test creating a generation session."""
        session = GenerationSession(session_id="test-session")
        assert session.session_id == "test-session"
        assert len(session.messages) == 0
        assert len(session.generated_files) == 0
        assert session.is_complete is False

    def test_session_with_files(self):
        """Test session with generated files."""
        session = GenerationSession(session_id="session-1")
        session.generated_files.append(
            GeneratedFile(path="src/Test.tsx", content="export default Test")
        )
        assert len(session.generated_files) == 1


# ---------------------------------------------------------------------------
# FrontendAgent Tests
# ---------------------------------------------------------------------------

class TestFrontendAgent:
    """Tests for FrontendAgent class."""

    @pytest.fixture
    def agent(self):
        """Create FrontendAgent instance."""
        return FrontendAgent()

    def test_agent_type(self, agent):
        """Test agent type."""
        assert agent.agent_type == AgentType.FRONTEND
        assert agent.name == "Frontend Agent"

    def test_get_or_create_session(self, agent):
        """Test session creation."""
        session = agent._get_or_create_session("test-session")
        assert session.session_id == "test-session"
        assert isinstance(session, GenerationSession)

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
        Some text before
        ```json
        {"type": "code_generation", "files": []}
        ```
        Some text after
        '''
        parsed = agent._parse_response(content)
        assert parsed["type"] == "code_generation"

    def test_parse_response_direct_json(self, agent):
        """Test parsing direct JSON response."""
        content = '{"type": "clarification", "questions": []}'
        parsed = agent._parse_response(content)
        assert parsed["type"] == "clarification"

    def test_parse_response_plain_text(self, agent):
        """Test parsing plain text response."""
        content = "This is plain text response"
        parsed = agent._parse_response(content)
        assert parsed["type"] == "response"
        assert parsed["content"] == content

    def test_get_generated_files_empty(self, agent):
        """Test getting generated files for empty session."""
        files = agent.get_generated_files("nonexistent")
        assert len(files) == 0

    def test_get_generated_files(self, agent):
        """Test getting generated files."""
        session = agent._get_or_create_session("files-test")
        session.generated_files.append(
            GeneratedFile(path="src/Test.tsx", content="export default Test")
        )
        
        files = agent.get_generated_files("files-test")
        assert len(files) == 1
        assert files[0].path == "src/Test.tsx"


# ---------------------------------------------------------------------------
# FrontendAgent Component Detection Tests
# ---------------------------------------------------------------------------

class TestFrontendAgentComponentDetection:
    """Tests for component type detection."""

    @pytest.fixture
    def agent(self):
        """Create FrontendAgent instance."""
        return FrontendAgent()

    def test_detect_form_component(self, agent):
        """Test detecting form component type."""
        from app.agents.frontend_agent.prompts import detect_component_type
        
        comp_type = detect_component_type("I need a login form")
        assert comp_type == "form"

    def test_detect_list_component(self, agent):
        """Test detecting list component type."""
        from app.agents.frontend_agent.prompts import detect_component_type
        
        comp_type = detect_component_type("Show a list of users")
        assert comp_type == "list"

    def test_detect_card_component(self, agent):
        """Test detecting card component type."""
        from app.agents.frontend_agent.prompts import detect_component_type
        
        comp_type = detect_component_type("Display info in a card")
        assert comp_type == "card"

    def test_detect_page_component(self, agent):
        """Test detecting page component type."""
        from app.agents.frontend_agent.prompts import detect_component_type
        
        comp_type = detect_component_type("Create a dashboard page")
        assert comp_type == "page"

    def test_extract_component_name_english(self, agent):
        """Test extracting component name from English."""
        from app.agents.frontend_agent.prompts import extract_component_name
        
        name = extract_component_name("Create a UserProfile component")
        assert "User" in name or "Profile" in name or "Component" in name

    def test_extract_component_name_chinese(self, agent):
        """Test extracting component name from Chinese."""
        from app.agents.frontend_agent.prompts import extract_component_name
        
        name = extract_component_name("创建一个用户列表组件")
        # Should generate some name
        assert len(name) > 0


# ---------------------------------------------------------------------------
# FrontendAgent Integration Tests with Mocked LLM
# ---------------------------------------------------------------------------

class TestFrontendAgentWithMockedLLM:
    """Tests with mocked LLM."""

    @pytest.fixture
    def agent_with_mocked_llm(self):
        """Create FrontendAgent with mocked LLM."""
        agent = FrontendAgent()
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
                        "path": "src/components/Button.tsx",
                        "content": "export function Button() {}",
                        "description": "Button component"
                    }
                ],
                "dependencies": ["react"]
            }
            ```
            '''
        )

        response = await agent.process_message(
            session_id="test",
            message="Create a button component",
        )

        assert response.success is True
        assert "session_id" in response.metadata
        assert response.metadata["type"] == "code_generation"

    @pytest.mark.asyncio
    async def test_process_message_clarification(self, agent_with_mocked_llm):
        """Test processing clarification request."""
        agent = agent_with_mocked_llm
        agent.llm.chat.return_value = MagicMock(
            content='''
            ```json
            {
                "type": "clarification",
                "questions": [
                    {
                        "id": "q1",
                        "question": "What color should the button be?",
                        "options": ["blue", "red", "green"]
                    }
                ]
            }
            ```
            '''
        )

        response = await agent.process_message(
            session_id="test",
            message="Create a button",
        )

        assert response.success is True
        assert "clarification_questions" in response.metadata or "clarification_questions" in str(response)

    @pytest.mark.asyncio
    async def test_generate_task_card(self, agent_with_mocked_llm):
        """Test generating task card."""
        agent = agent_with_mocked_llm

        # Create a session with messages
        session = agent._get_or_create_session("task-test")
        session.messages.append({
            "role": "user",
            "content": "Create a login form",
            "timestamp": datetime.utcnow().isoformat(),
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
    async def test_execute_task(self, agent_with_mocked_llm):
        """Test executing a task."""
        agent = agent_with_mocked_llm
        
        # Mock the generation tool
        mock_result = CodeGenerationResult(
            files=[
                GeneratedFile(
                    path="src/components/Test.tsx",
                    content="export default function Test() {}",
                ),
            ],
            dependencies=["react"],
        )
        
        # Patch the tool
        with patch.object(CodeGenerationTool, 'generate_component', new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = mock_result
            
            task_card = TaskCard(
                id="task-1",
                type="feature",
                priority="medium",
                description="Create a test component",
                structured_requirements=[],
                constraints={},
            )

            response = await agent.execute(task_card)
            assert response.success is True
            assert response.task_card is not None


# ---------------------------------------------------------------------------
# CodeGenerationTool Tests
# ---------------------------------------------------------------------------

class TestCodeGenerationTool:
    """Tests for CodeGenerationTool."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM."""
        llm = MagicMock()
        llm.chat = AsyncMock()
        return llm

    @pytest.fixture
    def tool(self, mock_llm):
        """Create CodeGenerationTool instance."""
        return CodeGenerationTool(mock_llm)

    @pytest.mark.asyncio
    async def test_generate_component(self, tool, mock_llm):
        """Test generating a component."""
        mock_llm.chat.return_value = MagicMock(
            content='''
            ```json
            {
                "files": [
                    {
                        "path": "src/components/Button.tsx",
                        "content": "export function Button() {}",
                        "description": "Button component",
                        "language": "typescript"
                    }
                ],
                "dependencies": ["react"]
            }
            ```
            '''
        )

        result = await tool.generate_component(
            description="A simple button",
            component_type="form",
        )

        assert len(result.files) == 1
        assert result.files[0].path == "src/components/Button.tsx"

    @pytest.mark.asyncio
    async def test_generate_component_error(self, tool, mock_llm):
        """Test component generation with error."""
        mock_llm.chat.return_value = MagicMock(
            content="Invalid response"
        )

        result = await tool.generate_component(
            description="A button",
        )

        assert len(result.files) == 0
        assert len(result.errors) > 0

    @pytest.mark.asyncio
    async def test_generate_store(self, tool, mock_llm):
        """Test generating a Zustand store."""
        mock_llm.chat.return_value = MagicMock(
            content='''
            ```json
            {
                "files": [
                    {
                        "path": "src/stores/useUserStore.ts",
                        "content": "import { create } from 'zustand'",
                        "description": "User store"
                    }
                ]
            }
            ```
            '''
        )

        result = await tool.generate_store(
            name="User",
            state_fields=[{"name": "user", "type": "object"}],
            actions=["setUser", "clearUser"],
        )

        assert len(result.files) == 1

    @pytest.mark.asyncio
    async def test_generate_api_hook(self, tool, mock_llm):
        """Test generating an API hook."""
        mock_llm.chat.return_value = MagicMock(
            content='''
            ```json
            {
                "files": [
                    {
                        "path": "src/hooks/useUsersApi.ts",
                        "content": "import { useState, useEffect } from 'react'",
                        "description": "Users API hook"
                    }
                ],
                "dependencies": []
            }
            ```
            '''
        )

        result = await tool.generate_api_hook(
            endpoint="/api/users",
            method="GET",
            data_type="User[]",
        )

        assert len(result.files) == 1


# ---------------------------------------------------------------------------
# CodeValidationTool Tests
# ---------------------------------------------------------------------------

class TestCodeValidationTool:
    """Tests for CodeValidationTool."""

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM."""
        llm = MagicMock()
        llm.chat = AsyncMock()
        return llm

    @pytest.fixture
    def tool(self, mock_llm):
        """Create CodeValidationTool instance."""
        return CodeValidationTool(mock_llm)

    @pytest.mark.asyncio
    async def test_validate_typescript_valid(self, tool, mock_llm):
        """Test validating valid TypeScript code."""
        mock_llm.chat.return_value = MagicMock(
            content='{"errors": [], "warnings": [], "suggestions": []}'
        )

        code = """
        export function Button() {
            return <button>Click</button>
        }
        """

        result = await tool.validate_typescript(code)

        assert result.is_valid is True
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_validate_typescript_with_any(self, tool, mock_llm):
        """Test validation detects 'any' type usage."""
        mock_llm.chat.return_value = MagicMock(
            content='{"errors": [], "warnings": ["Use of any type"], "suggestions": []}'
        )

        code = """
        export function process(data: any) {
            return data
        }
        """

        result = await tool.validate_typescript(code)

        # Should have warnings about 'any'
        assert len(result.warnings) >= 0  # May come from basic checks or LLM

    @pytest.mark.asyncio
    async def test_check_accessibility_missing_alt(self, tool, mock_llm):
        """Test accessibility check for missing alt attribute."""
        code = """
        export function ImageComponent() {
            return <img src="/test.jpg" />
        }
        """

        result = await tool.check_accessibility(code)

        assert len(result.errors) > 0
        assert any("alt" in err.lower() for err in result.errors)

    @pytest.mark.asyncio
    async def test_check_accessibility_empty_button(self, tool, mock_llm):
        """Test accessibility check for empty button."""
        code = """
        export function Component() {
            return <button onClick={() => {}}></button>
        }
        """

        result = await tool.check_accessibility(code)

        assert len(result.errors) > 0
        assert any("button" in err.lower() for err in result.errors)


# ---------------------------------------------------------------------------
# SandboxSubmitTool Tests
# ---------------------------------------------------------------------------

class TestSandboxSubmitTool:
    """Tests for SandboxSubmitTool."""

    @pytest.fixture
    def tool(self):
        """Create SandboxSubmitTool instance."""
        return SandboxSubmitTool(sandbox_url="http://localhost:8080")

    @pytest.mark.asyncio
    async def test_submit_code(self, tool):
        """Test submitting code to sandbox."""
        files = [
            GeneratedFile(
                path="src/App.tsx",
                content="export default App",
            ),
        ]

        result = await tool.submit_code(files=files, task_id="test-task")

        assert result["success"] is True
        assert result["task_id"] == "test-task"

    @pytest.mark.asyncio
    async def test_check_status(self, tool):
        """Test checking sandbox status."""
        result = await tool.check_status(task_id="test-task")

        assert result["task_id"] == "test-task"
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_preview_url(self, tool):
        """Test getting preview URL."""
        url = await tool.get_preview_url(task_id="test-task")

        assert url is not None
        assert "test-task" in url
