"""Frontend Agent package for UI code generation."""

from app.agents.frontend_agent.agent import FrontendAgent, GenerationSession
from app.agents.frontend_agent.prompts import (
    API_HOOK_TEMPLATE,
    CODE_GENERATION_PROMPT,
    COMPONENT_TEMPLATES,
    FRONTEND_SYSTEM_PROMPT,
    WEBSOCKET_HOOK_TEMPLATE,
    detect_component_type,
    extract_component_name,
    get_component_template,
    get_system_prompt,
)
from app.agents.frontend_agent.tools import (
    CodeGenerationResult,
    CodeGenerationTool,
    CodeValidationTool,
    GeneratedFile,
    SandboxSubmitTool,
    ValidationResult,
)

__all__ = [
    # Agent
    "FrontendAgent",
    "GenerationSession",
    # Prompts
    "FRONTEND_SYSTEM_PROMPT",
    "COMPONENT_TEMPLATES",
    "API_HOOK_TEMPLATE",
    "WEBSOCKET_HOOK_TEMPLATE",
    "CODE_GENERATION_PROMPT",
    "get_system_prompt",
    "get_component_template",
    "detect_component_type",
    "extract_component_name",
    # Tools
    "CodeGenerationTool",
    "CodeGenerationResult",
    "CodeValidationTool",
    "ValidationResult",
    "SandboxSubmitTool",
    "GeneratedFile",
]