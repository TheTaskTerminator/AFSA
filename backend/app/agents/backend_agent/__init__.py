"""Backend Agent package for API and database code generation."""

from app.agents.backend_agent.agent import BackendAgent, BackendSession
from app.agents.backend_agent.prompts import (
    API_ENDPOINT_TEMPLATE,
    API_GENERATION_PROMPT,
    BACKEND_SYSTEM_PROMPT,
    MODEL_TEMPLATE,
    REPOSITORY_TEMPLATE,
    SCHEMA_TEMPLATE,
    detect_api_type,
    extract_model_name,
    get_api_template,
    get_model_template,
    get_schema_template,
    get_system_prompt,
)
from app.agents.backend_agent.tools import (
    APIGenerationResult,
    APIGenerationTool,
    APISpec,
    CodeReviewTool,
    GeneratedFile,
    ModelDefinition,
    SchemaGenerationTool,
)

__all__ = [
    # Agent
    "BackendAgent",
    "BackendSession",
    # Prompts
    "BACKEND_SYSTEM_PROMPT",
    "API_ENDPOINT_TEMPLATE",
    "MODEL_TEMPLATE",
    "SCHEMA_TEMPLATE",
    "REPOSITORY_TEMPLATE",
    "API_GENERATION_PROMPT",
    "get_system_prompt",
    "get_api_template",
    "get_model_template",
    "get_schema_template",
    "detect_api_type",
    "extract_model_name",
    # Tools
    "APIGenerationTool",
    "APIGenerationResult",
    "APISpec",
    "SchemaGenerationTool",
    "CodeReviewTool",
    "GeneratedFile",
    "ModelDefinition",
]