"""Framework adapter interface and implementations.

This module provides adapters for different agent frameworks:
- LangGraph: State-based workflow with graph nodes
- CrewAI: Role-based agent collaboration
- AutoGen: Multi-agent conversation

The adapters allow seamless switching between frameworks
while maintaining a consistent interface for the application.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

from app.agents.base import AgentResponse, BaseAgent, TaskCard


class WorkflowState(str, Enum):
    """Workflow execution state."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WorkflowContext:
    """Context for workflow execution."""

    session_id: str
    task_card: Optional[TaskCard] = None
    state: WorkflowState = WorkflowState.PENDING
    messages: List[Dict[str, Any]] = field(default_factory=list)
    memory: Dict[str, Any] = field(default_factory=dict)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


class FrameworkAdapter(ABC):
    """Abstract base class for framework adapters.

    Each adapter wraps a specific agent framework and provides
    a unified interface for agent creation and workflow execution.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._workflows: Dict[str, WorkflowContext] = {}

    @abstractmethod
    async def create_agent(
        self,
        agent_class: Type[BaseAgent],
        config: Optional[Dict[str, Any]] = None,
    ) -> BaseAgent:
        """Create an agent instance using the framework.

        Args:
            agent_class: The agent class to instantiate
            config: Optional configuration for the agent

        Returns:
            Configured agent instance
        """
        pass

    @abstractmethod
    async def run_workflow(
        self,
        agent: BaseAgent,
        task_card: TaskCard,
        context: Optional[WorkflowContext] = None,
    ) -> AgentResponse:
        """Run the agent workflow.

        Args:
            agent: The agent to run
            task_card: Task specification
            context: Optional workflow context for stateful execution

        Returns:
            Agent response with results
        """
        pass

    @abstractmethod
    async def resume_workflow(
        self,
        session_id: str,
        agent: BaseAgent,
    ) -> AgentResponse:
        """Resume a paused workflow.

        Args:
            session_id: Session to resume
            agent: The agent to continue

        Returns:
            Agent response with results
        """
        pass

    def get_context(self, session_id: str) -> Optional[WorkflowContext]:
        """Get workflow context by session ID."""
        return self._workflows.get(session_id)

    def store_context(self, context: WorkflowContext) -> None:
        """Store workflow context."""
        self._workflows[context.session_id] = context


class LangGraphAdapter(FrameworkAdapter):
    """LangGraph framework adapter.

    LangGraph provides stateful, multi-actor applications with LLMs.
    It uses a graph-based approach for workflow management.

    Features:
    - State machine for workflow states
    - Conditional edges for branching logic
    - Checkpointing for persistence
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._graph = None

    async def create_agent(
        self,
        agent_class: Type[BaseAgent],
        config: Optional[Dict[str, Any]] = None,
    ) -> BaseAgent:
        """Create an agent using LangGraph."""
        agent = agent_class()

        # Store config in agent if needed
        if config:
            agent._langgraph_config = config

        return agent

    async def _build_graph(self, agent: BaseAgent) -> Any:
        """Build LangGraph state graph for the agent."""
        try:
            from langgraph.graph import StateGraph, END

            # Define state schema
            from typing import TypedDict

            class AgentState(TypedDict):
                messages: List[Dict[str, Any]]
                task_card: Optional[Dict[str, Any]]
                current_step: str
                output: Optional[str]
                errors: List[str]

            # Create graph
            workflow = StateGraph(AgentState)

            # Add nodes
            async def process_node(state: AgentState) -> AgentState:
                """Process the task."""
                if state["task_card"]:
                    task_card = TaskCard(**state["task_card"])
                    response = await agent.execute(task_card)
                    state["output"] = response.content
                    state["errors"] = [e for e in [response.metadata.get("error")] if e]
                state["current_step"] = "completed"
                return state

            workflow.add_node("process", process_node)
            workflow.add_edge("process", END)
            workflow.set_entry_point("process")

            return workflow.compile()

        except ImportError:
            # LangGraph not installed, use simple execution
            return None

    async def run_workflow(
        self,
        agent: BaseAgent,
        task_card: TaskCard,
        context: Optional[WorkflowContext] = None,
    ) -> AgentResponse:
        """Run LangGraph workflow."""
        # Create or use existing context
        if context is None:
            context = WorkflowContext(
                session_id=task_card.id,
                task_card=task_card,
                state=WorkflowState.RUNNING,
            )

        try:
            # Build graph if not cached
            graph = await self._build_graph(agent)

            if graph:
                # Run with LangGraph
                initial_state = {
                    "messages": context.messages,
                    "task_card": {
                        "id": task_card.id,
                        "type": task_card.type,
                        "priority": task_card.priority,
                        "description": task_card.description,
                        "structured_requirements": task_card.structured_requirements,
                        "constraints": task_card.constraints,
                        "timeout_seconds": task_card.timeout_seconds,
                    },
                    "current_step": "start",
                    "output": None,
                    "errors": [],
                }

                result = await graph.ainvoke(initial_state)

                context.state = WorkflowState.COMPLETED
                context.artifacts["output"] = result.get("output")
                context.errors = result.get("errors", [])

                self.store_context(context)

                return AgentResponse(
                    success=len(context.errors) == 0,
                    content=result.get("output", ""),
                    metadata={"framework": "langgraph", "state": context.state.value},
                )
            else:
                # Fallback to direct execution
                response = await agent.execute(task_card)
                context.state = WorkflowState.COMPLETED
                self.store_context(context)
                return response

        except Exception as e:
            context.state = WorkflowState.FAILED
            context.errors.append(str(e))
            self.store_context(context)

            return AgentResponse(
                success=False,
                content="",
                metadata={"error": str(e), "framework": "langgraph"},
            )

    async def resume_workflow(
        self,
        session_id: str,
        agent: BaseAgent,
    ) -> AgentResponse:
        """Resume a paused workflow."""
        context = self.get_context(session_id)
        if not context:
            return AgentResponse(
                success=False,
                content="",
                metadata={"error": f"Session {session_id} not found"},
            )

        if context.state != WorkflowState.PAUSED:
            return AgentResponse(
                success=False,
                content="",
                metadata={"error": f"Workflow is {context.state.value}, not paused"},
            )

        if context.task_card:
            return await self.run_workflow(agent, context.task_card, context)

        return AgentResponse(
            success=False,
            content="",
            metadata={"error": "No task card in context"},
        )


class CrewAIAdapter(FrameworkAdapter):
    """CrewAI framework adapter.

    CrewAI enables orchestrating role-playing AI agents.
    It focuses on collaborative AI agent teams.

    Features:
    - Role-based agent definitions
    - Task delegation between agents
    - Sequential and hierarchical processes
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

    async def create_agent(
        self,
        agent_class: Type[BaseAgent],
        config: Optional[Dict[str, Any]] = None,
    ) -> BaseAgent:
        """Create an agent using CrewAI."""
        agent = agent_class()

        if config:
            agent._crewai_config = config

        return agent

    async def run_workflow(
        self,
        agent: BaseAgent,
        task_card: TaskCard,
        context: Optional[WorkflowContext] = None,
    ) -> AgentResponse:
        """Run CrewAI workflow."""
        if context is None:
            context = WorkflowContext(
                session_id=task_card.id,
                task_card=task_card,
                state=WorkflowState.RUNNING,
            )

        try:
            # Check if CrewAI is available
            try:
                from crewai import Agent, Crew, Task

                # Create CrewAI agent wrapper
                crew_agent = Agent(
                    role=agent.name or "AI Agent",
                    goal=f"Complete task: {task_card.description}",
                    backstory="An AI agent working on software development tasks.",
                    allow_delegation=False,
                    verbose=self.config.get("verbose", False),
                )

                # Create task
                crew_task = Task(
                    description=task_card.description,
                    agent=crew_agent,
                    expected_output="Completed task with results",
                )

                # Create and run crew
                crew = Crew(
                    agents=[crew_agent],
                    tasks=[crew_task],
                    verbose=self.config.get("verbose", False),
                )

                result = await crew.kickoff_async()

                context.state = WorkflowState.COMPLETED
                context.artifacts["output"] = result
                self.store_context(context)

                return AgentResponse(
                    success=True,
                    content=str(result),
                    metadata={"framework": "crewai"},
                )

            except ImportError:
                # CrewAI not installed, use fallback
                response = await agent.execute(task_card)
                context.state = WorkflowState.COMPLETED
                self.store_context(context)
                return response

        except Exception as e:
            context.state = WorkflowState.FAILED
            context.errors.append(str(e))
            self.store_context(context)

            return AgentResponse(
                success=False,
                content="",
                metadata={"error": str(e), "framework": "crewai"},
            )

    async def resume_workflow(
        self,
        session_id: str,
        agent: BaseAgent,
    ) -> AgentResponse:
        """Resume a paused workflow."""
        context = self.get_context(session_id)
        if not context or not context.task_card:
            return AgentResponse(
                success=False,
                content="",
                metadata={"error": f"Cannot resume session {session_id}"},
            )

        return await self.run_workflow(agent, context.task_card, context)


class AutoGenAdapter(FrameworkAdapter):
    """AutoGen framework adapter.

    AutoGen enables building multi-agent conversations.
    It focuses on autonomous agent interactions.

    Features:
    - Conversable agents
    - Multi-agent conversation patterns
    - Code execution integration
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

    async def create_agent(
        self,
        agent_class: Type[BaseAgent],
        config: Optional[Dict[str, Any]] = None,
    ) -> BaseAgent:
        """Create an agent using AutoGen."""
        agent = agent_class()

        if config:
            agent._autogen_config = config

        return agent

    async def run_workflow(
        self,
        agent: BaseAgent,
        task_card: TaskCard,
        context: Optional[WorkflowContext] = None,
    ) -> AgentResponse:
        """Run AutoGen workflow."""
        if context is None:
            context = WorkflowContext(
                session_id=task_card.id,
                task_card=task_card,
                state=WorkflowState.RUNNING,
            )

        try:
            # Check if AutoGen is available
            try:
                import autogen

                # Create AutoGen agent configuration
                config_list = [
                    {
                        "model": self.config.get("model", "gpt-4"),
                    }
                ]

                # Create assistant agent
                assistant = autogen.AssistantAgent(
                    name=agent.name or "assistant",
                    llm_config={"config_list": config_list},
                    system_message=f"You are a helpful AI assistant. Task: {task_card.description}",
                )

                # Create user proxy for interaction
                user_proxy = autogen.UserProxyAgent(
                    name="user_proxy",
                    human_input_mode="NEVER",
                    max_consecutive_auto_reply=self.config.get("max_turns", 10),
                    code_execution_config={
                        "work_dir": self.config.get("work_dir", "."),
                        "use_docker": False,
                    },
                )

                # Initiate chat
                user_proxy.initiate_chat(
                    assistant,
                    message=task_card.description,
                )

                # Get last message from assistant
                last_message = assistant.last_message()
                result = last_message.get("content", "") if last_message else ""

                context.state = WorkflowState.COMPLETED
                context.artifacts["output"] = result
                self.store_context(context)

                return AgentResponse(
                    success=True,
                    content=result,
                    metadata={"framework": "autogen"},
                )

            except ImportError:
                # AutoGen not installed, use fallback
                response = await agent.execute(task_card)
                context.state = WorkflowState.COMPLETED
                self.store_context(context)
                return response

        except Exception as e:
            context.state = WorkflowState.FAILED
            context.errors.append(str(e))
            self.store_context(context)

            return AgentResponse(
                success=False,
                content="",
                metadata={"error": str(e), "framework": "autogen"},
            )

    async def resume_workflow(
        self,
        session_id: str,
        agent: BaseAgent,
    ) -> AgentResponse:
        """Resume a paused workflow."""
        context = self.get_context(session_id)
        if not context or not context.task_card:
            return AgentResponse(
                success=False,
                content="",
                metadata={"error": f"Cannot resume session {session_id}"},
            )

        return await self.run_workflow(agent, context.task_card, context)


def get_adapter(framework: str, config: Optional[Dict[str, Any]] = None) -> FrameworkAdapter:
    """Get framework adapter by name.

    Args:
        framework: Framework name (langgraph, crewai, autogen)
        config: Optional configuration for the adapter

    Returns:
        Framework adapter instance
    """
    adapters = {
        "langgraph": LangGraphAdapter,
        "crewai": CrewAIAdapter,
        "autogen": AutoGenAdapter,
    }
    adapter_class = adapters.get(framework, LangGraphAdapter)
    return adapter_class(config)