"""
AFSA Agents Package

Agent 系统模块：
- PM Agent: 产品经理智能体
- Architect Agent: 架构师智能体
- Frontend Agent: 前端开发智能体
- Backend Agent: 后端开发智能体
- Data Agent: 数据工程师智能体
"""

from app.agents.base import (
    BaseAgent,
    AgentResponse,
    TaskCard,
    TaskType,
    TaskPriority,
    TaskStatus,
    AgentType,
    RequirementSpec,
    tool,
    create_agent,
)

from app.agents.pm_agent import PMAgent, create_pm_agent
from app.agents.architect_agent import (
    ArchitectAgent,
    ArchitectSession,
    ArchitectureImpact,
    FeasibilityResult,
    ImpactLevel,
    PerformanceImpact,
    ReviewResult,
    ReviewStatus,
    SecurityFinding,
    ZoneViolation,
)
from app.agents.frontend_agent import (
    FrontendAgent,
    GenerationSession,
    CodeGenerationTool,
    CodeValidationTool,
    GeneratedFile,
    CodeGenerationResult,
    ValidationResult as FrontendValidationResult,
)
from app.agents.backend_agent import (
    BackendAgent,
    BackendSession,
    APIGenerationTool,
    SchemaGenerationTool,
    CodeReviewTool,
    GeneratedFile as BackendGeneratedFile,
    APIGenerationResult,
)
from app.agents.data_agent import (
    DataAgent,
    DataSession,
    ColumnDefinition,
    TableDefinition,
    MigrationFile,
    MigrationType,
    MigrationStatus,
    SchemaAnalysis,
    SchemaChangeImpact,
    DataChangeResult,
    ValidationResult as DataValidationResult,
)

__all__ = [
    # Base
    "BaseAgent",
    "AgentResponse",
    "TaskCard",
    "TaskType",
    "TaskPriority",
    "TaskStatus",
    "AgentType",
    "RequirementSpec",
    "tool",
    "create_agent",
    
    # PM Agent
    "PMAgent",
    "create_pm_agent",
    
    # Architect Agent
    "ArchitectAgent",
    "ArchitectSession",
    "ArchitectureImpact",
    "FeasibilityResult",
    "ImpactLevel",
    "PerformanceImpact",
    "ReviewResult",
    "ReviewStatus",
    "SecurityFinding",
    "ZoneViolation",
    
    # Frontend Agent
    "FrontendAgent",
    "GenerationSession",
    "CodeGenerationTool",
    "CodeValidationTool",
    "GeneratedFile",
    "CodeGenerationResult",
    "FrontendValidationResult",
    
    # Backend Agent
    "BackendAgent",
    "BackendSession",
    "APIGenerationTool",
    "SchemaGenerationTool",
    "CodeReviewTool",
    "BackendGeneratedFile",
    "APIGenerationResult",
    
    # Data Agent
    "DataAgent",
    "DataSession",
    "ColumnDefinition",
    "TableDefinition",
    "MigrationFile",
    "MigrationType",
    "MigrationStatus",
    "SchemaAnalysis",
    "SchemaChangeImpact",
    "DataChangeResult",
    "DataValidationResult",
]
