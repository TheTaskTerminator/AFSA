"""PM Agent package for requirement analysis and task management."""

from typing import Any, Dict, Optional

from app.agents.pm_agent.agent import ConversationState, PMAgent
from app.agents.pm_agent.prompts import (
    CLARIFICATION_TEMPLATES,
    PRIORITY_KEYWORDS,
    PM_SYSTEM_PROMPT,
    TASK_CARD_GENERATION_PROMPT,
    TASK_TYPE_KEYWORDS,
    detect_priority,
    detect_task_type,
    get_clarification_questions,
    get_system_prompt,
)
from app.agents.pm_agent.tools import (
    ClarificationResult,
    ClarificationTool,
    ContextCompressionTool,
    TaskAnalysisResult,
    TaskAnalysisTool,
)

def create_pm_agent(config: Optional[Dict[str, Any]] = None) -> PMAgent:
    """Create a PM Agent instance.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        PMAgent instance
    """
    return PMAgent(config=config)


__all__ = [
    # Agent
    "PMAgent",
    "ConversationState",
    "create_pm_agent",
    # Prompts
    "PM_SYSTEM_PROMPT",
    "CLARIFICATION_TEMPLATES",
    "TASK_TYPE_KEYWORDS",
    "PRIORITY_KEYWORDS",
    "TASK_CARD_GENERATION_PROMPT",
    "get_system_prompt",
    "get_clarification_questions",
    "detect_task_type",
    "detect_priority",
    # Tools
    "ClarificationTool",
    "ClarificationResult",
    "TaskAnalysisTool",
    "TaskAnalysisResult",
    "ContextCompressionTool",
]