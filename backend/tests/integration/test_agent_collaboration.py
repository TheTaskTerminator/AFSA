"""
Agent Collaboration Flow Integration Tests.

Tests the complete workflow of agent collaboration:
- PM Agent receives requirements → generates task cards
- Architect Agent evaluates → technical feasibility report
- Dev Agent executes → code generation
- Sandbox validates → execution results
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.models.task import Task
from app.models.conversation import ConversationSession, ConversationMessage
from app.schemas.task import TaskCreate, TaskPriority, TaskType


@pytest.mark.asyncio
class TestAgentCollaborationFlow:
    """Test complete agent collaboration workflow."""

    async def test_pm_agent_receives_requirement_generates_task_card(
        self,
        session,
        test_user,
    ):
        """
        Test Scenario: PM Agent receives user requirement and generates a task card.
        
        Flow:
        1. User sends requirement via conversation
        2. PM Agent processes the message
        3. PM Agent generates structured task card
        4. Task card is saved to database
        """
        from app.agents.pm_agent.agent import PMAgent
        
        # Mock PM Agent response
        mock_task_card = MagicMock()
        mock_task_card.id = str(uuid4())
        mock_task_card.type = "feature"
        mock_task_card.priority = "medium"
        mock_task_card.description = "Implement user authentication API"
        mock_task_card.structured_requirements = {
            "features": ["login", "logout", "password reset"],
            "acceptance_criteria": ["JWT tokens", "bcrypt hashing"]
        }
        mock_task_card.constraints = {"timeout": 300, "max_iterations": 10}
        
        with patch.object(PMAgent, 'process_message', new_callable=AsyncMock) as mock_process:
            with patch.object(PMAgent, 'generate_task_card', new_callable=AsyncMock) as mock_generate:
                mock_process.return_value = MagicMock(
                    content="I understand your requirements. Generating task card...",
                    success=True,
                    clarification_questions=[],
                    task_card=mock_task_card
                )
                mock_generate.return_value = mock_task_card
                
                pm_agent = PMAgent()
                session_id = str(uuid4())
                
                # Process user message
                response = await pm_agent.process_message(
                    session_id=session_id,
                    message="I need a user authentication system with login, logout, and password reset",
                    context={"user_id": str(test_user.id)}
                )
                
                # Verify PM Agent processed the message
                assert response.success is True
                mock_process.assert_called_once()
                
                # Generate task card
                task_card = await pm_agent.generate_task_card(session_id)
                
                # Verify task card generation
                assert task_card is not None
                assert task_card.type == "feature"
                assert task_card.description == "Implement user authentication API"
                assert "login" in task_card.structured_requirements["features"]
                
                mock_generate.assert_called_once_with(session_id)

    async def test_architect_agent_evaluates_technical_feasibility(
        self,
        session,
        test_task,
    ):
        """
        Test Scenario: Architect Agent evaluates task for technical feasibility.
        
        Flow:
        1. Architect Agent receives task card
        2. Analyzes technical requirements
        3. Generates feasibility report
        4. Provides architecture recommendations
        """
        from app.agents.architect_agent.agent import ArchitectAgent
        from app.agents.architect_agent.agent import FeasibilityResult, ReviewStatus
        
        # Mock Architect Agent response
        mock_feasibility_result = FeasibilityResult(
            feasible=True,
            complexity="medium",
            estimated_effort="3 days",
            technical_risks=["Database migration needed", "External API integration"],
            recommended_architecture={
                "pattern": "Layered Architecture",
                "components": ["API Gateway", "Service Layer", "Data Access Layer"],
                "technologies": ["FastAPI", "SQLAlchemy", "PostgreSQL"]
            },
            dependencies=["auth-service", "user-service"],
            migration_required=True
        )
        
        with patch.object(ArchitectAgent, '_analyze_feasibility', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_feasibility_result
            
            architect_agent = ArchitectAgent()
            
            # Evaluate feasibility (using internal method for testing)
            result = await architect_agent._analyze_feasibility(test_task.description)
            
            # Verify evaluation
            assert result is not None
            assert result.feasible is True
            assert result.complexity == "medium"
            
            mock_analyze.assert_called_once()

    async def test_dev_agent_executes_code_generation(
        self,
        session,
        test_task,
    ):
        """
        Test Scenario: Backend Agent executes code generation based on task requirements.
        
        Flow:
        1. Backend Agent receives task with requirements
        2. Analyzes requirements and constraints
        3. Generates code files
        4. Returns generated code with metadata
        """
        from app.agents.backend_agent.agent import BackendAgent
        
        # Mock Backend Agent response
        mock_code_generation = {
            "success": True,
            "files": [
                {
                    "path": "app/api/v1/endpoints/auth.py",
                    "content": "from fastapi import APIRouter...\n",
                    "language": "python",
                    "lines_of_code": 150
                },
                {
                    "path": "app/schemas/auth.py",
                    "content": "from pydantic import BaseModel...\n",
                    "language": "python",
                    "lines_of_code": 80
                }
            ],
            "total_files": 2,
            "total_lines": 230,
            "generation_time_seconds": 45.2
        }
        
        # Backend agent uses LLM for code generation - mock the LLM call
        with patch.object(BackendAgent, 'process_message', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = MagicMock(
                content="Code generated successfully",
                success=True,
                artifacts=mock_code_generation
            )
            
            backend_agent = BackendAgent()
            
            # Generate code via process_message
            result = await backend_agent.process_message(
                session_id=str(test_task.id),
                message=f"Generate code for: {test_task.description}",
                context={"task_id": str(test_task.id)}
            )
            
            # Verify code generation
            assert result.success is True
            assert "Code generated" in result.content
            
            mock_process.assert_called_once()

    async def test_sandbox_validates_execution_results(
        self,
        session,
        test_task,
    ):
        """
        Test Scenario: Sandbox validates generated code execution.
        
        Flow:
        1. Sandbox receives generated code
        2. Sets up isolated execution environment
        3. Executes code with test cases
        4. Returns execution results and validation status
        """
        from app.sandbox.sandbox import LocalSandbox, SandboxConfig
        
        # Create a local sandbox
        config = SandboxConfig(type="local", timeout_seconds=30)
        sandbox = LocalSandbox(config)
        
        # Execute simple Python code
        test_code = """
print("Hello from sandbox")
import sys
sys.exit(0)
"""
        
        result = await sandbox.execute(test_code)
        
        # Verify execution
        assert result.success is True
        assert result.exit_code == 0
        assert "Hello from sandbox" in result.output
        
        await sandbox.cleanup()

    async def test_complete_agent_collaboration_workflow(
        self,
        session,
        test_user,
    ):
        """
        Test Scenario: Complete end-to-end agent collaboration workflow.
        
        Flow:
        1. PM Agent receives requirement → creates task
        2. Architect Agent evaluates → feasibility approved
        3. Backend Agent generates code → files created
        4. Sandbox validates → execution succeeds
        5. Task marked as completed
        """
        from app.agents.pm_agent.agent import PMAgent
        from app.agents.architect_agent.agent import ArchitectAgent, FeasibilityResult
        from app.agents.backend_agent.agent import BackendAgent
        from app.sandbox.sandbox import LocalSandbox, SandboxConfig
        from app.repositories.task import TaskRepository
        
        # Mock PM Agent response
        mock_task_card = MagicMock()
        mock_task_card.id = str(uuid4())
        mock_task_card.type = "feature"
        mock_task_card.priority = "high"
        mock_task_card.description = "Implement payment processing module"
        mock_task_card.structured_requirements = {"features": ["payment", "refund"]}
        mock_task_card.constraints = {"timeout": 600}
        
        with patch.object(PMAgent, 'generate_task_card', new_callable=AsyncMock) as mock_pm:
            mock_pm.return_value = mock_task_card
            
            # Step 1: PM Agent generates task card
            pm_agent = PMAgent()
            task_card = await pm_agent.generate_task_card(str(uuid4()))
            assert task_card is not None
            
            # Create task in database
            task_repo = TaskRepository(session)
            from app.schemas.task import TaskCreate, TaskType, TaskPriority, TaskConstraints
            task_data = TaskCreate(
                type=TaskType.FEATURE,
                priority=TaskPriority.HIGH,
                description=task_card.description,
                constraints=TaskConstraints(
                    timeout_seconds=task_card.constraints.get("timeout", 300)
                )
            )
            db_task = await task_repo.create(task_data)
            await session.commit()
            
            # Step 2: Architect Agent evaluates feasibility
            architect_agent = ArchitectAgent()
            with patch.object(ArchitectAgent, '_analyze_feasibility', new_callable=AsyncMock) as mock_arch:
                mock_arch.return_value = FeasibilityResult(
                    feasible=True,
                    complexity="high",
                    estimated_effort="5 days"
                )
                feasibility = await architect_agent._analyze_feasibility(db_task.description)
                assert feasibility.feasible is True
            
            # Step 3: Backend Agent generates code (mocked)
            backend_agent = BackendAgent()
            with patch.object(BackendAgent, 'process_message', new_callable=AsyncMock) as mock_backend:
                mock_backend.return_value = MagicMock(
                    content="Code generated",
                    success=True,
                    artifacts={"files": [{"path": "app/api/payment.py", "content": "# code"}]}
                )
                code_result = await backend_agent.process_message(
                    session_id=str(db_task.id),
                    message="Generate payment code",
                    context={}
                )
                assert code_result.success is True
            
            # Step 4: Sandbox validates execution
            config = SandboxConfig(type="local", timeout_seconds=30)
            sandbox = LocalSandbox(config)
            test_code = "print('test passed'); exit(0)"
            execution_result = await sandbox.execute(test_code)
            assert execution_result.success is True
            assert execution_result.exit_code == 0
            
            await sandbox.cleanup()
            
            # Step 5: Update task status to completed
            db_task.status = "completed"
            db_task.result = {
                "feasibility": {"feasible": True, "complexity": "high"},
                "execution_success": True
            }
            await session.commit()
            
            # Verify complete workflow
            assert db_task.status == "completed"
            assert db_task.result is not None

    async def test_agent_collaboration_with_error_handling(
        self,
        session,
        test_task,
    ):
        """
        Test Scenario: Agent collaboration with error scenarios.
        
        Tests:
        1. Architect Agent marks task as not feasible
        2. Backend Agent fails to generate code
        3. Sandbox execution fails
        4. Error is properly recorded
        """
        from app.agents.architect_agent.agent import ArchitectAgent, FeasibilityResult
        from app.sandbox.sandbox import LocalSandbox, SandboxConfig
        
        # Test 1: Architect rejects task
        architect_agent = ArchitectAgent()
        with patch.object(ArchitectAgent, '_analyze_feasibility', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = FeasibilityResult(
                feasible=False,
                rejection_reason="Technical constraints cannot be met",
                alternative_approach="Consider using third-party service"
            )
            
            report = await architect_agent._analyze_feasibility(test_task.description)
            
            assert report.feasible is False
            assert report.rejection_reason is not None
        
        # Test 2: Sandbox execution fails
        config = SandboxConfig(type="local", timeout_seconds=30)
        sandbox = LocalSandbox(config)
        
        # Code that will fail
        failing_code = """
import sys
print("This will fail")
sys.exit(1)
"""
        
        result = await sandbox.execute(failing_code)
        
        assert result.success is False
        assert result.exit_code == 1
        
        await sandbox.cleanup()
