"""
AFSA Agents Package

Agent 系统模块：
- PM Agent: 产品经理智能体
- Architect Agent: 架构师智能体 (待实现)
- Frontend Agent: 前端开发智能体 (待实现)
- Backend Agent: 后端开发智能体 (待实现)
- Data Agent: 数据工程师智能体 (待实现)
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
]
