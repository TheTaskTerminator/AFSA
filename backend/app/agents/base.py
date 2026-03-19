"""
AFSA Agent Base Classes

Agent 系统的基础类和接口定义。
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import uuid


# ============= 枚举类型 =============

class TaskType(str, Enum):
    """任务类型"""
    FEATURE = "feature"
    BUGFIX = "bugfix"
    CONFIG = "config"
    REFACTOR = "refactor"


class TaskPriority(str, Enum):
    """任务优先级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, Enum):
    """任务状态"""
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentType(str, Enum):
    """Agent 类型"""
    PM = "pm"
    ARCHITECT = "architect"
    FRONTEND = "frontend"
    BACKEND = "backend"
    DATA = "data"
    CUSTOM = "custom"


# ============= 数据模型 =============

class RequirementSpec(BaseModel):
    """需求规格"""
    type: str  # model, api, ui, workflow, feature
    name: str
    spec: Dict[str, Any]
    constraints: Dict[str, Any] = Field(default_factory=dict)


class TaskCard(BaseModel):
    """任务卡 - 结构化的开发任务定义"""
    
    # 基本标识
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: TaskType
    priority: TaskPriority = TaskPriority.MEDIUM
    description: str
    
    # 结构化需求
    requirements: List[RequirementSpec] = Field(default_factory=list)
    
    # 约束条件
    target_zone: str = "mutable"
    timeout_seconds: int = 300
    requires_approval: bool = True
    
    # 生命周期
    status: TaskStatus = TaskStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    created_by: str = "user"
    approved_by: Optional[str] = None
    
    # 执行结果
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    # 元数据
    session_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    
    # 协议版本
    protocol_version: str = "1.0"
    
    def mark_running(self) -> None:
        """标记任务为运行中"""
        self.status = TaskStatus.RUNNING
        self.updated_at = datetime.now(timezone.utc)
    
    def mark_completed(self, result: Dict[str, Any]) -> None:
        """标记任务为完成"""
        self.status = TaskStatus.COMPLETED
        self.result = result
        self.updated_at = datetime.now(timezone.utc)
    
    def mark_failed(self, error: str) -> None:
        """标记任务为失败"""
        self.status = TaskStatus.FAILED
        self.error_message = error
        self.updated_at = datetime.now(timezone.utc)


class AgentResponse(BaseModel):
    """Agent 响应"""
    success: bool
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    
    @classmethod
    def ok(cls, content: str, metadata: Optional[Dict[str, Any]] = None) -> "AgentResponse":
        """创建成功响应"""
        return cls(success=True, content=content, metadata=metadata or {})
    
    @classmethod
    def error(cls, message: str, metadata: Optional[Dict[str, Any]] = None) -> "AgentResponse":
        """创建错误响应"""
        return cls(success=False, content="", error=message, metadata=metadata or {})


# ============= Agent 基类 =============

class BaseAgent(ABC):
    """所有 Agent 的抽象基类
    
    每个 Agent 必须实现：
    1. process_message - 处理用户消息
    2. generate_task_card - 生成任务卡
    3. execute - 执行任务
    """
    
    # 类变量 - 子类必须定义
    agent_type: AgentType = AgentType.CUSTOM
    name: str = "Unnamed Agent"
    description: str = "Base agent"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化 Agent
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self._tools: Dict[str, Any] = {}
        self._llm: Optional[Any] = None
    
    @abstractmethod
    async def process_message(
        self,
        session_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """处理用户消息
        
        Args:
            session_id: 会话 ID
            message: 用户消息
            context: 上下文信息
            
        Returns:
            AgentResponse: 响应
        """
        pass
    
    @abstractmethod
    async def generate_task_card(self, session_id: str) -> Optional[TaskCard]:
        """从当前会话生成任务卡
        
        Args:
            session_id: 会话 ID
            
        Returns:
            生成的任务卡，如果信息不足则返回 None
        """
        pass
    
    @abstractmethod
    async def execute(self, task_card: TaskCard) -> AgentResponse:
        """执行任务卡
        
        Args:
            task_card: 任务卡
            
        Returns:
            AgentResponse: 执行结果
        """
        pass
    
    # ============= 工具管理 =============
    
    def register_tool(self, name: str, tool: Any) -> None:
        """注册工具
        
        Args:
            name: 工具名称
            tool: 工具实例
        """
        self._tools[name] = tool
    
    def get_tool(self, name: str) -> Optional[Any]:
        """获取工具
        
        Args:
            name: 工具名称
            
        Returns:
            工具实例，如果不存在则返回 None
        """
        return self._tools.get(name)
    
    def list_tools(self) -> List[str]:
        """列出所有已注册的工具名称"""
        return list(self._tools.keys())
    
    # ============= LLM 访问 =============
    
    def set_llm(self, llm: Any) -> None:
        """设置 LLM 实例
        
        Args:
            llm: LLM 实例
        """
        self._llm = llm
    
    def get_llm(self) -> Optional[Any]:
        """获取 LLM 实例"""
        return self._llm
    
    # ============= 辅助方法 =============
    
    def get_info(self) -> Dict[str, str]:
        """获取 Agent 信息"""
        return {
            "type": self.agent_type.value,
            "name": self.name,
            "description": self.description,
            "tools": self.list_tools(),
        }


# ============= 工具装饰器 =============

def tool(func):
    """工具装饰器
    
    用于标记一个方法为工具方法
    
    使用示例:
        class MyAgent(BaseAgent):
            @tool
            async def query_database(self, sql: str):
                \"\"\"查询数据库\"\"\"
                pass
    """
    func._is_tool = True
    func._tool_name = func.__name__
    return func


# ============= 工厂函数 =============

def create_agent(agent_type: AgentType, config: Optional[Dict[str, Any]] = None) -> BaseAgent:
    """创建 Agent 实例
    
    Args:
        agent_type: Agent 类型
        config: 配置字典
        
    Returns:
        Agent 实例
        
    Raises:
        ValueError: 未知的 Agent 类型
    """
    # 延迟导入以避免循环依赖
    if agent_type == AgentType.PM:
        from app.agents.pm_agent import PMAgent
        return PMAgent(config=config)
    
    # 其他类型待实现
    raise ValueError(f"Unknown agent type: {agent_type}")
