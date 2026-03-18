"""Agent abstract base class and framework adapters."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class AgentType(str, Enum):
    """Agent types."""
    PM = "pm"
    FRONTEND = "frontend"
    BACKEND = "backend"
    DATA = "data"
    ARCHITECT = "architect"


@dataclass
class TaskCard:
    """Structured task card for agent execution."""
    id: str
    type: str  # feature|bugfix|config
    priority: str  # high|medium|low
    description: str
    structured_requirements: List[Dict[str, Any]]
    constraints: Dict[str, Any]
    timeout_seconds: int = 300


@dataclass
class AgentResponse:
    """Agent response."""
    success: bool
    content: str
    metadata: Optional[Dict[str, Any]] = None
    task_card: Optional[TaskCard] = None
    clarification_questions: Optional[List[str]] = None


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    agent_type: AgentType
    name: str

    @abstractmethod
    async def process_message(
        self,
        session_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Process a user message."""
        pass

    @abstractmethod
    async def generate_task_card(self, session_id: str) -> Optional[TaskCard]:
        """Generate a structured task card from the conversation."""
        pass

    @abstractmethod
    async def execute(self, task_card: TaskCard) -> AgentResponse:
        """Execute the task."""
        pass

    def get_name(self) -> str:
        """Get agent name."""
        return self.name

    def get_type(self) -> AgentType:
        """Get agent type."""
        return self.agent_type