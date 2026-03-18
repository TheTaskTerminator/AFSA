"""Tests for agent protocol module."""
import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import AgentResponse as BaseAgentResponse
from app.agents.base import AgentType, BaseAgent, TaskCard
from app.agents.protocol.coordinator import (
    AgentTask,
    CollaborationResult,
    WorkflowCoordinator,
    WorkflowStage,
    WorkflowStageResult,
    WorkflowStatus,
)
from app.agents.protocol.message import (
    AgentMessage,
    AgentMessageType,
    AgentRequest,
    AgentResponse,
    BroadcastMessage,
    CollaborationContext,
    MessagePriority,
    MessageStatus,
    RequestType,
    ResponseStatus,
)
from app.agents.protocol.router import (
    AgentRouter,
    MessageRoute,
    RoutingAction,
    RoutingRule,
)


# ============== Test Fixtures ==============


@pytest.fixture
def sample_task_card() -> TaskCard:
    """Create a sample task card."""
    return TaskCard(
        id=str(uuid.uuid4()),
        type="feature",
        priority="high",
        description="Add user authentication feature",
        structured_requirements=[
            {"type": "model", "name": "User", "fields": ["id", "email", "password"]},
            {"type": "api", "name": "login", "method": "POST"},
        ],
        constraints={"framework": "fastapi"},
    )


@pytest.fixture
def sample_context(sample_task_card: TaskCard) -> CollaborationContext:
    """Create a sample collaboration context."""
    return CollaborationContext(
        workflow_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        original_request="Add user authentication",
        task_card=sample_task_card,
    )


@pytest.fixture
def mock_agent() -> BaseAgent:
    """Create a mock agent for testing."""

    class MockAgent(BaseAgent):
        agent_type = AgentType.BACKEND
        name = "Mock Backend Agent"

        async def process_message(
            self, session_id: str, message: str, context: Optional[Dict[str, Any]] = None
        ) -> BaseAgentResponse:
            return BaseAgentResponse(success=True, content="Processed")

        async def generate_task_card(self, session_id: str) -> Optional[TaskCard]:
            return None

        async def execute(self, task_card: TaskCard) -> BaseAgentResponse:
            return BaseAgentResponse(success=True, content="Executed")

    return MockAgent()


# ============== Message Tests ==============


class TestCollaborationContext:
    """Tests for CollaborationContext."""

    def test_create_context(self) -> None:
        """Test creating a collaboration context."""
        context = CollaborationContext(
            workflow_id="wf-123",
            session_id="sess-456",
            original_request="Test request",
        )

        assert context.workflow_id == "wf-123"
        assert context.session_id == "sess-456"
        assert context.original_request == "Test request"
        assert context.shared_data == {}
        assert context.agent_results == {}

    def test_update_shared_data(self, sample_context: CollaborationContext) -> None:
        """Test updating shared data."""
        sample_context.update("key1", "value1")

        assert sample_context.shared_data["key1"] == "value1"
        assert sample_context.updated_at >= sample_context.created_at

    def test_set_agent_result(self, sample_context: CollaborationContext) -> None:
        """Test setting agent result."""
        sample_context.set_agent_result(AgentType.BACKEND, {"code": "generated"})

        result = sample_context.get_agent_result(AgentType.BACKEND)
        assert result == {"code": "generated"}

    def test_context_serialization(self, sample_context: CollaborationContext) -> None:
        """Test context serialization."""
        data = sample_context.to_dict()

        assert "workflow_id" in data
        assert "session_id" in data
        assert "created_at" in data

        # Deserialize
        restored = CollaborationContext.from_dict(data)
        assert restored.workflow_id == sample_context.workflow_id
        assert restored.session_id == sample_context.session_id


class TestAgentMessage:
    """Tests for AgentMessage."""

    def test_create_message(self) -> None:
        """Test creating a basic message."""
        message = AgentMessage(
            message_id="msg-123",
            message_type=AgentMessageType.REQUEST,
            sender=AgentType.PM,
            receiver=AgentType.BACKEND,
            timestamp=datetime.utcnow(),
            payload={"test": "data"},
        )

        assert message.message_id == "msg-123"
        assert message.message_type == AgentMessageType.REQUEST
        assert message.sender == AgentType.PM
        assert message.receiver == AgentType.BACKEND

    def test_message_auto_id(self) -> None:
        """Test message auto-generates ID."""
        message = AgentMessage(
            message_id="",  # Empty ID should be auto-generated
            message_type=AgentMessageType.NOTIFICATION,
            sender=AgentType.PM,
            receiver=AgentType.BACKEND,
            timestamp=datetime.utcnow(),
        )

        assert message.message_id  # Should have a UUID

    def test_message_serialization(self) -> None:
        """Test message serialization."""
        message = AgentMessage(
            message_id="msg-123",
            message_type=AgentMessageType.REQUEST,
            sender=AgentType.PM,
            receiver=AgentType.BACKEND,
            timestamp=datetime.utcnow(),
            payload={"key": "value"},
        )

        data = message.to_dict()
        assert data["message_id"] == "msg-123"
        assert data["message_type"] == "request"

        # Deserialize
        restored = AgentMessage.from_dict(data)
        assert restored.message_id == message.message_id
        assert restored.sender == message.sender


class TestAgentRequest:
    """Tests for AgentRequest."""

    def test_create_request(self) -> None:
        """Test creating an agent request."""
        request = AgentRequest.create(
            sender=AgentType.PM,
            receiver=AgentType.BACKEND,
            request_type=RequestType.BACKEND_GENERATE,
            payload={"model": "User"},
        )

        assert request.message_type == AgentMessageType.REQUEST
        assert request.sender == AgentType.PM
        assert request.receiver == AgentType.BACKEND
        assert request.request_type == RequestType.BACKEND_GENERATE
        assert request.timeout_seconds == 300

    def test_request_with_context(
        self, sample_context: CollaborationContext
    ) -> None:
        """Test request with collaboration context."""
        request = AgentRequest.create(
            sender=AgentType.PM,
            receiver=AgentType.DATA,
            request_type=RequestType.DATA_SCHEMA,
            payload={"models": ["User"]},
            context=sample_context,
        )

        assert request.context is not None
        assert request.context.workflow_id == sample_context.workflow_id

    def test_request_serialization(self) -> None:
        """Test request serialization."""
        request = AgentRequest.create(
            sender=AgentType.PM,
            receiver=AgentType.ARCHITECT,
            request_type=RequestType.ARCHITECT_REVIEW,
            payload={"design": "test"},
            priority=MessagePriority.HIGH,
        )

        data = request.to_dict()
        assert data["request_type"] == "architect.review"
        assert data["priority"] == "high"

        restored = AgentRequest.from_dict(data)
        assert restored.request_type == request.request_type


class TestAgentResponse:
    """Tests for AgentResponse."""

    def test_create_response(self) -> None:
        """Test creating an agent response."""
        request = AgentRequest.create(
            sender=AgentType.PM,
            receiver=AgentType.BACKEND,
            request_type=RequestType.BACKEND_GENERATE,
            payload={"model": "User"},
        )

        response = AgentResponse.success(request, {"files": ["user.py"]})

        assert response.message_type == AgentMessageType.RESPONSE
        assert response.response_status == ResponseStatus.SUCCESS
        assert response.correlation_id == request.message_id
        assert response.result == {"files": ["user.py"]}

    def test_failure_response(self) -> None:
        """Test creating a failure response."""
        request = AgentRequest.create(
            sender=AgentType.PM,
            receiver=AgentType.DATA,
            request_type=RequestType.DATA_MIGRATION,
            payload={},
        )

        response = AgentResponse.failure(request, "Migration failed")

        assert response.response_status == ResponseStatus.FAILURE
        assert response.error_message == "Migration failed"

    def test_needs_clarification_response(self) -> None:
        """Test creating a clarification response."""
        request = AgentRequest.create(
            sender=AgentType.PM,
            receiver=AgentType.ARCHITECT,
            request_type=RequestType.ARCHITECT_REVIEW,
            payload={},
        )

        questions = ["What framework?", "Database type?"]
        response = AgentResponse.needs_clarification(request, questions)

        assert response.response_status == ResponseStatus.NEEDS_CLARIFICATION
        assert response.result == {"questions": questions}

    def test_partial_response(self) -> None:
        """Test creating a partial response."""
        request = AgentRequest.create(
            sender=AgentType.PM,
            receiver=AgentType.BACKEND,
            request_type=RequestType.BACKEND_GENERATE,
            payload={},
        )

        response = AgentResponse.failure(
            request,
            "Partial failure",
            partial_result={"completed": ["model.py"]},
        )

        assert response.response_status == ResponseStatus.PARTIAL
        assert response.result == {"completed": ["model.py"]}


class TestBroadcastMessage:
    """Tests for BroadcastMessage."""

    def test_create_broadcast(self) -> None:
        """Test creating a broadcast message."""
        broadcast = BroadcastMessage.create(
            sender=AgentType.PM,
            target_agents=[AgentType.BACKEND, AgentType.FRONTEND],
            payload={"event": "task_updated"},
        )

        assert broadcast.message_type == AgentMessageType.BROADCAST
        assert AgentType.BACKEND in broadcast.target_agents
        assert AgentType.FRONTEND in broadcast.target_agents

    def test_broadcast_serialization(self) -> None:
        """Test broadcast serialization."""
        broadcast = BroadcastMessage.create(
            sender=AgentType.ARCHITECT,
            target_agents=[AgentType.BACKEND, AgentType.DATA],
            payload={"review": "approved"},
        )

        data = broadcast.to_dict()
        assert "target_agents" in data

        restored = BroadcastMessage.from_dict(data)
        assert len(restored.target_agents) == 2


# ============== Router Tests ==============


class TestRoutingRule:
    """Tests for RoutingRule."""

    def test_create_rule(self) -> None:
        """Test creating a routing rule."""

        def condition(msg: AgentMessage) -> bool:
            return msg.priority == MessagePriority.CRITICAL

        rule = RoutingRule(
            name="critical_priority",
            condition=condition,
            action=RoutingAction.QUEUE,
            priority=1,
        )

        assert rule.name == "critical_priority"
        assert rule.action == RoutingAction.QUEUE

        # Test condition
        msg = AgentMessage(
            message_id="test",
            message_type=AgentMessageType.REQUEST,
            sender=AgentType.PM,
            receiver=AgentType.BACKEND,
            timestamp=datetime.utcnow(),
            priority=MessagePriority.CRITICAL,
        )
        assert rule.condition(msg) is True


class TestMessageRoute:
    """Tests for MessageRoute."""

    def test_create_route(self) -> None:
        """Test creating a message route."""
        route = MessageRoute(
            message_id="msg-123",
            source=AgentType.PM,
            targets=[AgentType.BACKEND],
            action=RoutingAction.DELIVER,
        )

        assert route.message_id == "msg-123"
        assert route.status == MessageStatus.PENDING
        assert AgentType.BACKEND in route.targets


class TestAgentRouter:
    """Tests for AgentRouter."""

    def test_create_router(self) -> None:
        """Test creating a router."""
        router = AgentRouter()
        assert router is not None
        assert len(router._agents) == 0

    def test_register_agent(self, mock_agent: BaseAgent) -> None:
        """Test registering an agent."""
        router = AgentRouter()
        router.register_agent(mock_agent)

        assert AgentType.BACKEND in router._agents
        assert router._agents[AgentType.BACKEND] == mock_agent

    def test_unregister_agent(self, mock_agent: BaseAgent) -> None:
        """Test unregistering an agent."""
        router = AgentRouter()
        router.register_agent(mock_agent)
        router.unregister_agent(AgentType.BACKEND)

        assert AgentType.BACKEND not in router._agents

    def test_add_rule(self) -> None:
        """Test adding a routing rule."""
        router = AgentRouter()
        rule = RoutingRule(
            name="test_rule",
            condition=lambda m: True,
            action=RoutingAction.DELIVER,
        )

        router.add_rule(rule)
        assert len(router._rules) == 1
        assert router._rules[0].name == "test_rule"

    def test_remove_rule(self) -> None:
        """Test removing a routing rule."""
        router = AgentRouter()
        rule = RoutingRule(
            name="test_rule",
            condition=lambda m: True,
            action=RoutingAction.DELIVER,
        )

        router.add_rule(rule)
        result = router.remove_rule("test_rule")

        assert result is True
        assert len(router._rules) == 0

    def test_remove_nonexistent_rule(self) -> None:
        """Test removing a rule that doesn't exist."""
        router = AgentRouter()
        result = router.remove_rule("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_route_message(self, mock_agent: BaseAgent) -> None:
        """Test routing a message."""
        router = AgentRouter()
        router.register_agent(mock_agent)

        message = AgentMessage(
            message_id="msg-123",
            message_type=AgentMessageType.NOTIFICATION,
            sender=AgentType.PM,
            receiver=AgentType.BACKEND,
            timestamp=datetime.utcnow(),
        )

        route = await router.route(message)

        assert route.status == MessageStatus.DELIVERED
        assert AgentType.BACKEND in route.targets

    @pytest.mark.asyncio
    async def test_determine_targets_for_request(self) -> None:
        """Test target determination for requests."""
        router = AgentRouter()

        request = AgentRequest.create(
            sender=AgentType.PM,
            receiver=AgentType.BACKEND,
            request_type=RequestType.BACKEND_GENERATE,
            payload={},
        )

        targets = router._determine_targets(
            request, RoutingAction.DELIVER, None
        )

        assert AgentType.BACKEND in targets

    def test_get_queue_size(self, mock_agent: BaseAgent) -> None:
        """Test getting queue size."""
        router = AgentRouter()
        router.register_agent(mock_agent)

        size = router.get_queue_size(AgentType.BACKEND)
        assert size == 0

        # Non-existent agent
        size = router.get_queue_size(AgentType.FRONTEND)
        assert size == 0


# ============== Coordinator Tests ==============


class TestWorkflowStageResult:
    """Tests for WorkflowStageResult."""

    def test_create_stage_result(self) -> None:
        """Test creating a stage result."""
        result = WorkflowStageResult(
            stage=WorkflowStage.REQUIREMENT_ANALYSIS,
            status=ResponseStatus.SUCCESS,
            result={"requirements": ["req1"]},
        )

        assert result.stage == WorkflowStage.REQUIREMENT_ANALYSIS
        assert result.is_success is True

    def test_stage_failure(self) -> None:
        """Test a failed stage result."""
        result = WorkflowStageResult(
            stage=WorkflowStage.ARCHITECTURE_REVIEW,
            status=ResponseStatus.FAILURE,
            error="Invalid architecture",
        )

        assert result.is_success is False
        assert result.error == "Invalid architecture"


class TestAgentTask:
    """Tests for AgentTask."""

    def test_create_agent_task(self) -> None:
        """Test creating an agent task."""
        task = AgentTask(
            task_id="task-123",
            agent_type=AgentType.BACKEND,
            request_type=RequestType.BACKEND_GENERATE,
            description="Generate user model",
            payload={"model": "User"},
        )

        assert task.task_id == "task-123"
        assert task.agent_type == AgentType.BACKEND
        assert task.status == WorkflowStatus.PENDING

    def test_task_auto_id(self) -> None:
        """Test task auto-generates ID."""
        task = AgentTask(
            task_id="",  # Empty should be auto-generated
            agent_type=AgentType.DATA,
            request_type=RequestType.DATA_MIGRATION,
            description="Migration task",
            payload={},
        )

        assert task.task_id  # Should have UUID


class TestCollaborationResult:
    """Tests for CollaborationResult."""

    def test_create_collaboration_result(self) -> None:
        """Test creating a collaboration result."""
        result = CollaborationResult(
            workflow_id="wf-123",
            status=WorkflowStatus.PENDING,
            stages=[],
        )

        assert result.workflow_id == "wf-123"
        assert result.status == WorkflowStatus.PENDING
        assert result.is_success is False

    def test_get_stage_result(self) -> None:
        """Test getting stage result."""
        result = CollaborationResult(
            workflow_id="wf-123",
            status=WorkflowStatus.RUNNING,
            stages=[
                WorkflowStageResult(
                    stage=WorkflowStage.REQUIREMENT_ANALYSIS,
                    status=ResponseStatus.SUCCESS,
                ),
                WorkflowStageResult(
                    stage=WorkflowStage.ARCHITECTURE_REVIEW,
                    status=ResponseStatus.SUCCESS,
                ),
            ],
        )

        stage_result = result.get_stage_result(WorkflowStage.REQUIREMENT_ANALYSIS)
        assert stage_result is not None
        assert stage_result.stage == WorkflowStage.REQUIREMENT_ANALYSIS

        # Non-existent stage
        stage_result = result.get_stage_result(WorkflowStage.TESTING)
        assert stage_result is None

    def test_result_serialization(self) -> None:
        """Test result serialization."""
        result = CollaborationResult(
            workflow_id="wf-123",
            status=WorkflowStatus.COMPLETED,
            stages=[
                WorkflowStageResult(
                    stage=WorkflowStage.BACKEND_IMPLEMENTATION,
                    status=ResponseStatus.SUCCESS,
                )
            ],
            final_result={"files": ["user.py"]},
        )

        data = result.to_dict()
        assert data["workflow_id"] == "wf-123"
        assert data["status"] == "completed"
        assert len(data["stages"]) == 1


class TestWorkflowCoordinator:
    """Tests for WorkflowCoordinator."""

    def test_create_coordinator(self) -> None:
        """Test creating a coordinator."""
        coordinator = WorkflowCoordinator()
        assert coordinator is not None

    def test_get_workflow_for_task(self) -> None:
        """Test getting workflow for task types."""
        coordinator = WorkflowCoordinator()

        # Feature workflow
        feature_workflow = coordinator.get_workflow_for_task("feature")
        assert len(feature_workflow) > 0
        assert (WorkflowStage.REQUIREMENT_ANALYSIS, AgentType.PM) in feature_workflow

        # Bugfix workflow
        bugfix_workflow = coordinator.get_workflow_for_task("bugfix")
        assert len(bugfix_workflow) > 0

    def test_register_custom_workflow(self) -> None:
        """Test registering a custom workflow."""
        coordinator = WorkflowCoordinator()

        custom_stages = [
            (WorkflowStage.REQUIREMENT_ANALYSIS, AgentType.PM),
            (WorkflowStage.COMPLETION, AgentType.PM),
        ]

        coordinator.register_workflow("simple", custom_stages)

        result = coordinator.get_workflow_for_task("simple")
        assert result == custom_stages

    def test_register_stage_handler(self) -> None:
        """Test registering a stage handler."""
        coordinator = WorkflowCoordinator()

        async def custom_handler(ctx: CollaborationContext) -> Dict[str, Any]:
            return {"custom": True}

        coordinator.register_stage_handler(
            WorkflowStage.REQUIREMENT_ANALYSIS, custom_handler
        )

        assert WorkflowStage.REQUIREMENT_ANALYSIS in coordinator._stage_handlers

    @pytest.mark.asyncio
    async def test_start_workflow(self, sample_task_card: TaskCard) -> None:
        """Test starting a workflow."""
        coordinator = WorkflowCoordinator()

        with patch.object(coordinator, "_execute_workflow", new_callable=AsyncMock):
            workflow_id = await coordinator.start_workflow(
                task_card=sample_task_card,
                session_id="test-session",
            )

            assert workflow_id is not None
            assert workflow_id in coordinator._workflows

    @pytest.mark.asyncio
    async def test_get_workflow_status(self, sample_task_card: TaskCard) -> None:
        """Test getting workflow status."""
        coordinator = WorkflowCoordinator()

        with patch.object(coordinator, "_execute_workflow", new_callable=AsyncMock):
            workflow_id = await coordinator.start_workflow(sample_task_card)

            status = await coordinator.get_workflow_status(workflow_id)
            assert status is not None
            assert status.workflow_id == workflow_id

    @pytest.mark.asyncio
    async def test_cancel_workflow(self, sample_task_card: TaskCard) -> None:
        """Test cancelling a workflow."""
        coordinator = WorkflowCoordinator()

        with patch.object(coordinator, "_execute_workflow", new_callable=AsyncMock):
            workflow_id = await coordinator.start_workflow(sample_task_card)

            # Cancel the workflow
            result = await coordinator.cancel_workflow(workflow_id)
            assert result is True

            status = await coordinator.get_workflow_status(workflow_id)
            assert status.status == WorkflowStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_pause_and_resume_workflow(self, sample_task_card: TaskCard) -> None:
        """Test pausing and resuming a workflow."""
        coordinator = WorkflowCoordinator()

        workflow_id = str(uuid.uuid4())
        result = CollaborationResult(
            workflow_id=workflow_id,
            status=WorkflowStatus.RUNNING,
            stages=[],
            context=CollaborationContext(
                workflow_id=workflow_id,
                session_id="test",
                original_request="test",
                task_card=sample_task_card,
            ),
        )
        coordinator._workflows[workflow_id] = result

        # Pause
        paused = await coordinator.pause_workflow(workflow_id)
        assert paused is True
        assert result.status == WorkflowStatus.PAUSED

    def test_build_stage_payload(self, sample_context: CollaborationContext) -> None:
        """Test building stage payload."""
        coordinator = WorkflowCoordinator()

        payload = coordinator._build_stage_payload(
            stage=WorkflowStage.BACKEND_IMPLEMENTATION,
            context=sample_context,
        )

        assert "stage" in payload
        assert "workflow_id" in payload
        assert payload["stage"] == "backend_implementation"

    def test_aggregate_results(self, sample_context: CollaborationContext) -> None:
        """Test aggregating results."""
        coordinator = WorkflowCoordinator()

        result = CollaborationResult(
            workflow_id="wf-123",
            status=WorkflowStatus.COMPLETED,
            stages=[
                WorkflowStageResult(
                    stage=WorkflowStage.REQUIREMENT_ANALYSIS,
                    status=ResponseStatus.SUCCESS,
                ),
                WorkflowStageResult(
                    stage=WorkflowStage.BACKEND_IMPLEMENTATION,
                    status=ResponseStatus.SUCCESS,
                ),
            ],
            context=sample_context,
        )

        aggregated = coordinator._aggregate_results(result)

        assert aggregated["workflow_id"] == "wf-123"
        assert aggregated["stages_completed"] == 2
        assert aggregated["total_stages"] == 2


# ============== Integration Tests ==============


class TestProtocolIntegration:
    """Integration tests for the protocol module."""

    @pytest.mark.asyncio
    async def test_request_response_flow(self) -> None:
        """Test complete request-response flow."""
        router = AgentRouter()

        # Create request
        request = AgentRequest.create(
            sender=AgentType.PM,
            receiver=AgentType.BACKEND,
            request_type=RequestType.BACKEND_GENERATE,
            payload={"model": "User"},
        )

        # Create success response
        response = AgentResponse.success(request, {"files": ["user.py"]})

        assert response.correlation_id == request.message_id
        assert response.response_status == ResponseStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_workflow_execution_flow(
        self, sample_task_card: TaskCard
    ) -> None:
        """Test workflow execution flow."""
        coordinator = WorkflowCoordinator()

        # Build payload for a stage
        context = CollaborationContext(
            workflow_id="wf-123",
            session_id="sess-456",
            original_request="Test request",
            task_card=sample_task_card,
        )

        payload = coordinator._build_stage_payload(
            stage=WorkflowStage.REQUIREMENT_ANALYSIS,
            context=context,
        )

        assert payload is not None
        assert "task_card" in payload


class TestEnumValues:
    """Tests for enum values."""

    def test_agent_message_type_values(self) -> None:
        """Test AgentMessageType enum values."""
        assert AgentMessageType.REQUEST.value == "request"
        assert AgentMessageType.RESPONSE.value == "response"
        assert AgentMessageType.BROADCAST.value == "broadcast"
        assert AgentMessageType.NOTIFICATION.value == "notification"

    def test_request_type_values(self) -> None:
        """Test RequestType enum values."""
        assert RequestType.ARCHITECT_REVIEW.value == "architect.review"
        assert RequestType.BACKEND_GENERATE.value == "backend.generate"
        assert RequestType.DATA_MIGRATION.value == "data.migration"

    def test_response_status_values(self) -> None:
        """Test ResponseStatus enum values."""
        assert ResponseStatus.SUCCESS.value == "success"
        assert ResponseStatus.FAILURE.value == "failure"
        assert ResponseStatus.PARTIAL.value == "partial"

    def test_workflow_stage_values(self) -> None:
        """Test WorkflowStage enum values."""
        assert WorkflowStage.INITIALIZATION.value == "initialization"
        assert WorkflowStage.REQUIREMENT_ANALYSIS.value == "requirement_analysis"
        assert WorkflowStage.BACKEND_IMPLEMENTATION.value == "backend_implementation"

    def test_workflow_status_values(self) -> None:
        """Test WorkflowStatus enum values."""
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowStatus.RUNNING.value == "running"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_payload(self) -> None:
        """Test messages with empty payload."""
        request = AgentRequest.create(
            sender=AgentType.PM,
            receiver=AgentType.BACKEND,
            request_type=RequestType.BACKEND_GENERATE,
            payload={},  # Empty payload
        )

        assert request.payload == {}

    def test_large_payload(self) -> None:
        """Test messages with large payload."""
        large_data = {f"key_{i}": f"value_{i}" * 100 for i in range(100)}

        request = AgentRequest.create(
            sender=AgentType.PM,
            receiver=AgentType.DATA,
            request_type=RequestType.DATA_SCHEMA,
            payload=large_data,
        )

        assert len(request.payload) == 100

    def test_unicode_in_payload(self) -> None:
        """Test messages with unicode characters."""
        request = AgentRequest.create(
            sender=AgentType.PM,
            receiver=AgentType.FRONTEND,
            request_type=RequestType.FRONTEND_GENERATE,
            payload={"description": "用户认证功能 🎉"},
        )

        assert "用户" in request.payload["description"]
        assert "🎉" in request.payload["description"]

    def test_message_with_none_values(self) -> None:
        """Test messages with None values."""
        request = AgentRequest.create(
            sender=AgentType.PM,
            receiver=AgentType.ARCHITECT,
            request_type=RequestType.ARCHITECT_REVIEW,
            payload={"optional": None},
        )

        response = AgentResponse.failure(request, None)  # type: ignore

        assert response.error_message is None