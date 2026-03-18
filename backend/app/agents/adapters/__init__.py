"""Framework adapters package.

This package provides adapters for different agent frameworks,
allowing seamless switching between implementations.
"""

from app.agents.adapters.base import (
    AutoGenAdapter,
    CrewAIAdapter,
    FrameworkAdapter,
    LangGraphAdapter,
    WorkflowContext,
    WorkflowState,
    get_adapter,
)

__all__ = [
    "FrameworkAdapter",
    "LangGraphAdapter",
    "CrewAIAdapter",
    "AutoGenAdapter",
    "WorkflowContext",
    "WorkflowState",
    "get_adapter",
]