"""PM Agent package for requirement analysis and task management."""

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

__all__ = [
    # Agent
    "PMAgent",
    "ConversationState",
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