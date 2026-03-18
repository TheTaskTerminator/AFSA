"""Workflow coordinator for multi-agent collaboration.

This module provides coordination capabilities for orchestrating
multi-agent workflows, ensuring proper sequencing and result aggregation.
"""
import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from app.agents.base import AgentResponse, AgentType, BaseAgent, TaskCard
from app.agents.protocol.message import (
    AgentRequest,
    AgentResponse as ProtocolResponse,
    CollaborationContext,
    MessagePriority,
    RequestType,
    ResponseStatus,
)
from app.agents.protocol.router import AgentRouter, get_router

logger = logging.getLogger(__name__)


class WorkflowStage(str, Enum):
    """Stages in a multi-agent workflow."""

    # Initial stage
    INITIALIZATION = "initialization"

    # Planning and analysis stages
    REQUIREMENT_ANALYSIS = "requirement_analysis"
    ARCHITECTURE_REVIEW = "architecture_review"

    # Implementation stages
    DATA_DESIGN = "data_design"
    BACKEND_IMPLEMENTATION = "backend_implementation"
    FRONTEND_IMPLEMENTATION = "frontend_implementation"

    # Validation stages
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    INTEGRATION = "integration"

    # Final stage
    COMPLETION = "completion"


class WorkflowStatus(str, Enum):
    """Status of a workflow."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStageResult:
    """Result from a workflow stage execution."""

    stage: WorkflowStage
    status: ResponseStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    agent_type: Optional[AgentType] = None

    @property
    def is_success(self) -> bool:
        """Check if stage completed successfully."""
        return self.status == ResponseStatus.SUCCESS

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get duration of stage execution."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass
class AgentTask:
    """A task assigned to a specific agent."""

    task_id: str
    agent_type: AgentType
    request_type: RequestType
    description: str
    payload: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    timeout_seconds: int = 300
    retry_count: int = 0
    max_retries: int = 2
    priority: MessagePriority = MessagePriority.NORMAL
    status: WorkflowStatus = WorkflowStatus.PENDING
    result: Optional[WorkflowStageResult] = None

    def __post_init__(self) -> None:
        """Generate task ID if not provided."""
        if not self.task_id:
            self.task_id = str(uuid.uuid4())


@dataclass
class CollaborationResult:
    """Final result of a multi-agent collaboration."""

    workflow_id: str
    status: WorkflowStatus
    stages: List[WorkflowStageResult]
    final_result: Optional[Any] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    context: Optional[CollaborationContext] = None

    @property
    def is_success(self) -> bool:
        """Check if workflow completed successfully."""
        return self.status == WorkflowStatus.COMPLETED

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get total duration of workflow."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def get_stage_result(self, stage: WorkflowStage) -> Optional[WorkflowStageResult]:
        """Get result for a specific stage."""
        for s in self.stages:
            if s.stage == stage:
                return s
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "stages": [
                {
                    "stage": s.stage.value,
                    "status": s.status.value,
                    "result": s.result,
                    "error": s.error,
                    "warnings": s.warnings,
                    "agent_type": s.agent_type.value if s.agent_type else None,
                }
                for s in self.stages
            ],
            "final_result": self.final_result,
            "errors": self.errors,
            "warnings": self.warnings,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


# Type for stage handlers
StageHandler = Callable[[CollaborationContext], Dict[str, Any]]


class WorkflowCoordinator:
    """Coordinator for multi-agent workflows.

    The coordinator manages the execution flow across multiple agents,
    handling dependencies, parallel execution, and result aggregation.
    """

    # Default workflow stages for a feature implementation
    DEFAULT_FEATURE_WORKFLOW = [
        (WorkflowStage.REQUIREMENT_ANALYSIS, AgentType.PM),
        (WorkflowStage.ARCHITECTURE_REVIEW, AgentType.ARCHITECT),
        (WorkflowStage.DATA_DESIGN, AgentType.DATA),
        (WorkflowStage.BACKEND_IMPLEMENTATION, AgentType.BACKEND),
        (WorkflowStage.FRONTEND_IMPLEMENTATION, AgentType.FRONTEND),
        (WorkflowStage.COMPLETION, AgentType.PM),
    ]

    # Default workflow for a bug fix
    DEFAULT_BUGFIX_WORKFLOW = [
        (WorkflowStage.REQUIREMENT_ANALYSIS, AgentType.PM),
        (WorkflowStage.ARCHITECTURE_REVIEW, AgentType.ARCHITECT),
        (WorkflowStage.BACKEND_IMPLEMENTATION, AgentType.BACKEND),
        (WorkflowStage.COMPLETION, AgentType.PM),
    ]

    def __init__(self, router: Optional[AgentRouter] = None) -> None:
        """Initialize the coordinator.

        Args:
            router: Optional router instance (uses global if not provided)
        """
        self._router = router or get_router()
        self._workflows: Dict[str, CollaborationResult] = {}
        self._stage_handlers: Dict[WorkflowStage, StageHandler] = {}
        self._custom_workflows: Dict[str, List[tuple[WorkflowStage, AgentType]]] = {}
        self._running = False
        self._active_tasks: Dict[str, asyncio.Task] = {}

    def register_stage_handler(
        self,
        stage: WorkflowStage,
        handler: StageHandler,
    ) -> None:
        """Register a custom handler for a workflow stage.

        Args:
            stage: The workflow stage
            handler: Async function to handle the stage
        """
        self._stage_handlers[stage] = handler
        logger.info(f"Registered handler for stage: {stage.value}")

    def register_workflow(
        self,
        name: str,
        stages: List[tuple[WorkflowStage, AgentType]],
    ) -> None:
        """Register a custom workflow definition.

        Args:
            name: Name of the workflow
            stages: List of (stage, agent_type) tuples
        """
        self._custom_workflows[name] = stages
        logger.info(f"Registered workflow: {name} with {len(stages)} stages")

    def get_workflow_for_task(self, task_type: str) -> List[tuple[WorkflowStage, AgentType]]:
        """Get the appropriate workflow for a task type.

        Args:
            task_type: Type of task (feature, bugfix, config)

        Returns:
            List of (stage, agent_type) tuples
        """
        # Check custom workflows first
        if task_type in self._custom_workflows:
            return self._custom_workflows[task_type]

        # Default workflows
        if task_type == "feature":
            return self.DEFAULT_FEATURE_WORKFLOW
        elif task_type == "bugfix":
            return self.DEFAULT_BUGFIX_WORKFLOW
        else:
            return self.DEFAULT_FEATURE_WORKFLOW

    async def start_workflow(
        self,
        task_card: TaskCard,
        session_id: Optional[str] = None,
    ) -> str:
        """Start a new workflow for a task.

        Args:
            task_card: The task card to process
            session_id: Optional session ID

        Returns:
            Workflow ID
        """
        workflow_id = str(uuid.uuid4())

        # Create collaboration context
        context = CollaborationContext(
            workflow_id=workflow_id,
            session_id=session_id or str(uuid.uuid4()),
            original_request=task_card.description,
            task_card=task_card,
        )

        # Get workflow stages
        stages = self.get_workflow_for_task(task_card.type)

        # Create workflow result
        result = CollaborationResult(
            workflow_id=workflow_id,
            status=WorkflowStatus.PENDING,
            stages=[],
            context=context,
        )
        self._workflows[workflow_id] = result

        # Start execution in background
        task = asyncio.create_task(self._execute_workflow(workflow_id, stages))
        self._active_tasks[workflow_id] = task

        logger.info(f"Started workflow {workflow_id} for task {task_card.id}")
        return workflow_id

    async def get_workflow_status(self, workflow_id: str) -> Optional[CollaborationResult]:
        """Get the current status of a workflow.

        Args:
            workflow_id: The workflow ID

        Returns:
            CollaborationResult if found, None otherwise
        """
        return self._workflows.get(workflow_id)

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow.

        Args:
            workflow_id: The workflow ID to cancel

        Returns:
            True if cancelled successfully
        """
        if workflow_id in self._active_tasks:
            task = self._active_tasks[workflow_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            if workflow_id in self._workflows:
                self._workflows[workflow_id].status = WorkflowStatus.CANCELLED

            logger.info(f"Cancelled workflow {workflow_id}")
            return True

        return False

    async def pause_workflow(self, workflow_id: str) -> bool:
        """Pause a running workflow.

        Args:
            workflow_id: The workflow ID to pause

        Returns:
            True if paused successfully
        """
        if workflow_id in self._workflows:
            self._workflows[workflow_id].status = WorkflowStatus.PAUSED
            logger.info(f"Paused workflow {workflow_id}")
            return True
        return False

    async def resume_workflow(self, workflow_id: str) -> bool:
        """Resume a paused workflow.

        Args:
            workflow_id: The workflow ID to resume

        Returns:
            True if resumed successfully
        """
        if workflow_id in self._workflows:
            result = self._workflows[workflow_id]
            if result.status == WorkflowStatus.PAUSED:
                result.status = WorkflowStatus.RUNNING
                # Restart execution from last incomplete stage
                stages = self.get_workflow_for_task(
                    result.context.task_card.type if result.context and result.context.task_card else "feature"
                )
                task = asyncio.create_task(
                    self._execute_workflow(workflow_id, stages, resume=True)
                )
                self._active_tasks[workflow_id] = task
                logger.info(f"Resumed workflow {workflow_id}")
                return True
        return False

    async def _execute_workflow(
        self,
        workflow_id: str,
        stages: List[tuple[WorkflowStage, AgentType]],
        resume: bool = False,
    ) -> None:
        """Execute the workflow stages.

        Args:
            workflow_id: The workflow ID
            stages: List of (stage, agent_type) tuples
            resume: Whether this is a resumed execution
        """
        result = self._workflows.get(workflow_id)
        if not result:
            logger.error(f"Workflow {workflow_id} not found")
            return

        result.status = WorkflowStatus.RUNNING

        # Find starting point if resuming
        start_index = 0
        if resume:
            completed_stages = {s.stage for s in result.stages if s.is_success}
            for i, (stage, _) in enumerate(stages):
                if stage not in completed_stages:
                    start_index = i
                    break

        try:
            for i, (stage, agent_type) in enumerate(stages[start_index:], start=start_index):
                # Check if workflow is paused or cancelled
                if result.status == WorkflowStatus.PAUSED:
                    logger.info(f"Workflow {workflow_id} paused at stage {stage.value}")
                    return

                if result.status == WorkflowStatus.CANCELLED:
                    logger.info(f"Workflow {workflow_id} cancelled at stage {stage.value}")
                    return

                # Execute stage
                stage_result = await self._execute_stage(
                    workflow_id=workflow_id,
                    stage=stage,
                    agent_type=agent_type,
                    context=result.context,
                )

                result.stages.append(stage_result)

                # Update context with stage result
                if stage_result.is_success and stage_result.result:
                    result.context.set_agent_result(agent_type, stage_result.result)
                    result.context.update(stage.value, stage_result.result)

                # Handle stage failure
                if not stage_result.is_success:
                    result.status = WorkflowStatus.FAILED
                    result.errors.append(f"Stage {stage.value} failed: {stage_result.error}")
                    logger.error(f"Workflow {workflow_id} failed at stage {stage.value}")
                    break

            # Mark as completed if all stages succeeded
            if result.status == WorkflowStatus.RUNNING:
                result.status = WorkflowStatus.COMPLETED
                result.completed_at = datetime.utcnow()
                result.final_result = self._aggregate_results(result)
                logger.info(f"Workflow {workflow_id} completed successfully")

        except asyncio.CancelledError:
            result.status = WorkflowStatus.CANCELLED
            logger.info(f"Workflow {workflow_id} was cancelled")

        except Exception as e:
            result.status = WorkflowStatus.FAILED
            result.errors.append(str(e))
            logger.error(f"Workflow {workflow_id} failed with error: {e}")

        finally:
            if workflow_id in self._active_tasks:
                del self._active_tasks[workflow_id]

    async def _execute_stage(
        self,
        workflow_id: str,
        stage: WorkflowStage,
        agent_type: AgentType,
        context: CollaborationContext,
    ) -> WorkflowStageResult:
        """Execute a single workflow stage.

        Args:
            workflow_id: The workflow ID
            stage: The stage to execute
            agent_type: The agent responsible for this stage
            context: The collaboration context

        Returns:
            WorkflowStageResult with execution outcome
        """
        stage_result = WorkflowStageResult(
            stage=stage,
            status=ResponseStatus.PENDING,
            agent_type=agent_type,
        )

        try:
            # Check for custom handler
            if stage in self._stage_handlers:
                result = self._stage_handlers[stage](context)
                stage_result.status = ResponseStatus.SUCCESS
                stage_result.result = result
            else:
                # Create and send request to agent
                request = self._create_stage_request(
                    stage=stage,
                    agent_type=agent_type,
                    context=context,
                )

                # Send request and wait for response
                response = await self._router.send_request(request)

                stage_result.status = response.response_status
                stage_result.result = response.result
                stage_result.error = response.error_message
                stage_result.warnings = response.warnings

            stage_result.completed_at = datetime.utcnow()

        except asyncio.TimeoutError:
            stage_result.status = ResponseStatus.FAILURE
            stage_result.error = "Stage execution timed out"
            stage_result.completed_at = datetime.utcnow()

        except Exception as e:
            stage_result.status = ResponseStatus.FAILURE
            stage_result.error = str(e)
            stage_result.completed_at = datetime.utcnow()

        return stage_result

    def _create_stage_request(
        self,
        stage: WorkflowStage,
        agent_type: AgentType,
        context: CollaborationContext,
    ) -> AgentRequest:
        """Create a request for a workflow stage.

        Args:
            stage: The workflow stage
            agent_type: The target agent
            context: The collaboration context

        Returns:
            AgentRequest for the stage
        """
        # Map stage to request type
        request_type_map = {
            WorkflowStage.REQUIREMENT_ANALYSIS: RequestType.PM_DISPATCH,
            WorkflowStage.ARCHITECTURE_REVIEW: RequestType.ARCHITECT_REVIEW,
            WorkflowStage.DATA_DESIGN: RequestType.DATA_SCHEMA,
            WorkflowStage.BACKEND_IMPLEMENTATION: RequestType.BACKEND_GENERATE,
            WorkflowStage.FRONTEND_IMPLEMENTATION: RequestType.FRONTEND_GENERATE,
            WorkflowStage.CODE_REVIEW: RequestType.ARCHITECT_REVIEW,
            WorkflowStage.TESTING: RequestType.BACKEND_VALIDATE,
            WorkflowStage.INTEGRATION: RequestType.PM_DISPATCH,
            WorkflowStage.COMPLETION: RequestType.PM_REPORT,
        }

        request_type = request_type_map.get(stage, RequestType.PM_DISPATCH)

        # Build payload based on stage and context
        payload = self._build_stage_payload(stage, context)

        return AgentRequest.create(
            sender=AgentType.PM,  # PM agent initiates by default
            receiver=agent_type,
            request_type=request_type,
            payload=payload,
            context=context,
        )

    def _build_stage_payload(
        self,
        stage: WorkflowStage,
        context: CollaborationContext,
    ) -> Dict[str, Any]:
        """Build the payload for a stage request.

        Args:
            stage: The workflow stage
            context: The collaboration context

        Returns:
            Dictionary with stage-specific payload
        """
        base_payload = {
            "stage": stage.value,
            "workflow_id": context.workflow_id,
            "session_id": context.session_id,
        }

        # Add context data
        if context.task_card:
            base_payload["task_card"] = {
                "id": context.task_card.id,
                "type": context.task_card.type,
                "description": context.task_card.description,
                "requirements": context.task_card.structured_requirements,
                "constraints": context.task_card.constraints,
            }

        # Add previous stage results
        if context.shared_data:
            base_payload["previous_results"] = context.shared_data

        # Stage-specific additions
        if stage == WorkflowStage.ARCHITECTURE_REVIEW:
            base_payload["review_type"] = "technical_feasibility"

        elif stage == WorkflowStage.DATA_DESIGN:
            if context.task_card:
                base_payload["models"] = [
                    r for r in context.task_card.structured_requirements
                    if r.get("type") == "model"
                ]

        elif stage == WorkflowStage.BACKEND_IMPLEMENTATION:
            # Include architecture review results
            arch_result = context.get_agent_result(AgentType.ARCHITECT)
            if arch_result:
                base_payload["architecture"] = arch_result

        elif stage == WorkflowStage.FRONTEND_IMPLEMENTATION:
            # Include backend API specs
            backend_result = context.get_agent_result(AgentType.BACKEND)
            if backend_result:
                base_payload["backend_apis"] = backend_result

        return base_payload

    def _aggregate_results(self, result: CollaborationResult) -> Dict[str, Any]:
        """Aggregate results from all stages.

        Args:
            result: The collaboration result

        Returns:
            Aggregated results dictionary
        """
        aggregated: Dict[str, Any] = {
            "workflow_id": result.workflow_id,
            "status": result.status.value,
            "stages_completed": len([s for s in result.stages if s.is_success]),
            "total_stages": len(result.stages),
        }

        if result.context:
            # Include agent results
            aggregated["agent_results"] = result.context.agent_results

            # Include any generated artifacts
            aggregated["artifacts"] = {}
            if result.context.task_card:
                aggregated["artifacts"]["task_id"] = result.context.task_card.id

        return aggregated


# Global coordinator instance
_coordinator: Optional[WorkflowCoordinator] = None


def get_coordinator() -> WorkflowCoordinator:
    """Get or create the global coordinator instance."""
    global _coordinator
    if _coordinator is None:
        _coordinator = WorkflowCoordinator()
    return _coordinator