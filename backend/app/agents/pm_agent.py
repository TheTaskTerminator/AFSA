"""
AFSA PM Agent - 产品经理智能体

负责：
- 自然语言需求理解
- 多轮对话澄清
- 生成结构化任务卡
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.agents.base import BaseAgent, AgentResponse, TaskCard, TaskType, TaskPriority, RequirementSpec


class AgentType:
    """Agent 类型定义"""
    PM = "pm"
    ARCHITECT = "architect"
    FRONTEND = "frontend"
    BACKEND = "backend"
    DATA = "data"


class PMAgent(BaseAgent):
    """产品经理 Agent
    
    作为用户与技术团队之间的桥梁，负责：
    1. 理解用户自然语言需求
    2. 通过多轮对话澄清模糊点
    3. 生成结构化的任务卡 (TaskCard)
    4. 协调其他 Agent 完成开发
    """
    
    agent_type = AgentType.PM
    name = "PM Agent"
    description = "Product Manager Agent - understands user requirements and generates task cards"
    
    # 需求类型关键词映射
    INTENT_KEYWORDS = {
        TaskType.FEATURE: ["新增", "添加", "实现", "创建", "开发", "功能", "feature", "add", "create"],
        TaskType.BUGFIX: ["修复", "bug", "错误", "问题", "故障", "fix", "bug", "error"],
        TaskType.CONFIG: ["配置", "设置", "调整", "修改参数", "config", "setting"],
        TaskType.REFACTOR: ["重构", "优化", "改进", "refactor", "optimize", "improve"],
    }
    
    # 需求澄清问题模板
    CLARIFICATION_QUESTIONS = {
        TaskType.FEATURE: [
            "这个功能的主要用户是谁？",
            "期望的使用场景是什么？",
            "有什么特定的业务规则吗？",
            "需要与现有系统集成吗？",
        ],
        TaskType.BUGFIX: [
            "问题出现的具体场景是什么？",
            "错误消息或表现是什么？",
            "问题出现的频率如何？",
            "影响的范围有多大？",
        ],
        TaskType.CONFIG: [
            "需要配置哪些具体参数？",
            "配置的作用范围是什么？",
            "有默认值要求吗？",
        ],
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化 PM Agent
        
        Args:
            config: 配置字典，可包含 LLM 配置等
        """
        super().__init__(config=config)
        self._conversation_history: List[Dict[str, str]] = []
        self._current_session: Optional[str] = None
        self._clarification_count: int = 0
        self._max_clarification_turns: int = 3
    
    async def process_message(
        self,
        session_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """处理用户消息
        
        流程：
        1. 更新对话历史
        2. 识别用户意图
        3. 判断是否需要澄清
        4. 如需要→生成澄清问题
        5. 如不需要→生成任务卡
        
        Args:
            session_id: 会话 ID
            message: 用户消息
            context: 上下文信息
            
        Returns:
            AgentResponse: 包含响应内容
        """
        self._current_session = session_id
        
        # 添加到对话历史
        self._conversation_history.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        # 识别意图
        intent = self._detect_intent(message)
        
        # 判断是否需要澄清
        needs_clarification = self._needs_clarification(message, intent)
        
        if needs_clarification and self._clarification_count < self._max_clarification_turns:
            # 生成澄清问题
            questions = self._generate_clarification_questions(intent, message)
            self._clarification_count += 1
            
            response_content = "\n".join([
                "为了更好地理解您的需求，我想确认几个问题：",
                "",
            ] + [f"{i+1}. {q}" for i, q in enumerate(questions)] + [
                "",
                "请回答这些问题，我会帮您生成具体的开发任务。",
            ])
            
            # 添加助手响应到历史
            self._conversation_history.append({
                "role": "assistant",
                "content": response_content,
                "timestamp": datetime.utcnow().isoformat(),
            })
            
            return AgentResponse(
                success=True,
                content=response_content,
                metadata={
                    "needs_clarification": True,
                    "intent": intent,
                    "clarification_turn": self._clarification_count,
                },
            )
        else:
            # 生成任务卡
            task_card = await self._generate_task_card_from_message(message, intent, context)
            
            # 重置澄清计数
            self._clarification_count = 0
            
            return AgentResponse(
                success=True,
                content=f"已理解您的需求，已生成开发任务：{task_card.id}",
                metadata={
                    "task_card": task_card.model_dump(),
                    "intent": intent,
                },
            )
    
    async def generate_task_card(self, session_id: str) -> Optional[TaskCard]:
        """从当前会话生成任务卡
        
        Args:
            session_id: 会话 ID
            
        Returns:
            生成的任务卡，如果信息不足则返回 None
        """
        if not self._conversation_history:
            return None
        
        # 合并所有用户消息
        user_messages = [
            msg["content"] for msg in self._conversation_history
            if msg["role"] == "user"
        ]
        
        combined_message = " ".join(user_messages)
        intent = self._detect_intent(combined_message)
        
        return await self._generate_task_card_from_message(
            combined_message,
            intent,
            {"session_id": session_id},
        )
    
    async def execute(self, task_card: TaskCard) -> AgentResponse:
        """执行任务卡
        
        对于 PM Agent，执行意味着协调其他 Agent 完成开发
        
        Args:
            task_card: 任务卡
            
        Returns:
            AgentResponse: 执行结果
        """
        # TODO: 实现多 Agent 协调逻辑
        # 1. 分发给 Architect Agent 进行技术评估
        # 2. 分发给 Dev Agents 进行开发
        # 3. 收集结果并汇总
        
        return AgentResponse(
            success=True,
            content=f"任务 {task_card.id} 已开始执行",
            metadata={
                "status": "in_progress",
                "task_card": task_card.model_dump(),
            },
        )
    
    def _detect_intent(self, message: str) -> TaskType:
        """检测用户意图
        
        基于关键词匹配识别需求类型
        
        Args:
            message: 用户消息
            
        Returns:
            TaskType: 识别的需求类型
        """
        message_lower = message.lower()
        
        scores = {}
        for task_type, keywords in self.INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in message_lower)
            scores[task_type] = score
        
        # 返回得分最高的类型
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        
        # 默认返回 FEATURE
        return TaskType.FEATURE
    
    def _needs_clarification(self, message: str, intent: TaskType) -> bool:
        """判断是否需要澄清
        
        判断标准：
        1. 消息长度过短 (< 20 字)
        2. 缺少关键信息
        3. 存在歧义
        
        Args:
            message: 用户消息
            intent: 识别的意图
            
        Returns:
            bool: 是否需要澄清
        """
        # 消息过短
        if len(message) < 20:
            return True
        
        # 检查是否包含具体功能描述
        if intent == TaskType.FEATURE:
            # 检查是否包含功能名称
            if not any(kw in message for kw in ["功能", "面板", "页面", "按钮", "列表", "表单"]):
                return True
        
        return False
    
    def _generate_clarification_questions(
        self,
        intent: TaskType,
        message: str,
    ) -> List[str]:
        """生成澄清问题
        
        Args:
            intent: 识别的意图
            message: 用户消息
            
        Returns:
            List[str]: 澄清问题列表
        """
        questions = []
        
        # 获取预定义问题模板
        templates = self.CLARIFICATION_QUESTIONS.get(intent, [])
        
        # 选择 2-3 个最相关的问题
        selected = templates[:min(3, len(templates))]
        
        # 根据具体消息定制问题
        if intent == TaskType.FEATURE:
            if "面板" in message or "可视化" in message:
                questions.append("需要展示哪些具体的数据指标？")
            if "用户" in message:
                questions.append("涉及哪些用户角色？")
        
        # 添加预定义问题
        questions.extend(selected)
        
        return questions[:3]  # 最多 3 个问题
    
    async def _generate_task_card_from_message(
        self,
        message: str,
        intent: TaskType,
        context: Optional[Dict[str, Any]],
    ) -> TaskCard:
        """从消息生成任务卡
        
        使用 LLM 将自然语言转换为结构化任务卡
        
        Args:
            message: 用户消息
            intent: 识别的意图
            context: 上下文信息
            
        Returns:
            TaskCard: 生成的任务卡
        """
        # 构建需求描述
        description = message
        
        # 如果有对话历史，合并上下文
        if len(self._conversation_history) > 1:
            context_messages = [
                msg["content"] for msg in self._conversation_history[:-1]
            ]
            description = "\n".join(context_messages + [message])
        
        # 生成结构化需求
        requirements = await self._extract_requirements(message, intent)
        
        # 确定优先级
        priority = self._determine_priority(message, intent)
        
        # 创建任务卡
        task_card = TaskCard(
            type=intent,
            priority=priority,
            description=description,
            requirements=requirements,
            session_id=context.get("session_id") if context else None,
            created_by="user",
        )
        
        return task_card
    
    async def _extract_requirements(
        self,
        message: str,
        intent: TaskType,
    ) -> List[RequirementSpec]:
        """从消息中提取结构化需求
        
        使用 LLM 或规则提取
        
        Args:
            message: 用户消息
            intent: 识别的意图
            
        Returns:
            List[RequirementSpec]: 需求规格列表
        """
        requirements = []
        
        # 简单规则提取 (后续用 LLM 增强)
        if intent == TaskType.FEATURE:
            # 检测 UI 相关关键词
            if any(kw in message for kw in ["面板", "页面", "界面", "按钮", "表单"]):
                requirements.append(RequirementSpec(
                    type="ui",
                    name="UI Component",
                    spec={"description": message},
                    constraints={"zone": "mutable"},
                ))
            
            # 检测数据相关关键词
            if any(kw in message for kw in ["数据", "查询", "统计", "报表"]):
                requirements.append(RequirementSpec(
                    type="model",
                    name="Data Model",
                    spec={"description": message},
                    constraints={"zone": "mutable"},
                ))
            
            # 检测 API 相关关键词
            if any(kw in message for kw in ["接口", "API", "服务"]):
                requirements.append(RequirementSpec(
                    type="api",
                    name="API Endpoint",
                    spec={"description": message},
                    constraints={},
                ))
        
        # 如果没有提取到具体需求，添加通用需求
        if not requirements:
            requirements.append(RequirementSpec(
                type="feature",
                name="General Feature",
                spec={"description": message},
                constraints={"zone": "mutable"},
            ))
        
        return requirements
    
    def _determine_priority(self, message: str, intent: TaskType) -> TaskPriority:
        """确定任务优先级
        
        Args:
            message: 用户消息
            intent: 识别的意图
            
        Returns:
            TaskPriority: 优先级
        """
        message_lower = message.lower()
        
        # 紧急关键词
        urgent_keywords = ["紧急", "urgent", "critical", "立即", "马上"]
        if any(kw in message_lower for kw in urgent_keywords):
            return TaskPriority.CRITICAL
        
        # 高优先级关键词
        high_keywords = ["重要", "important", "high", "优先"]
        if any(kw in message_lower for kw in high_keywords):
            return TaskPriority.HIGH
        
        # Bug 默认高优先级
        if intent == TaskType.BUGFIX:
            return TaskPriority.HIGH
        
        # 默认中优先级
        return TaskPriority.MEDIUM
    
    def reset_session(self, session_id: str) -> None:
        """重置会话
        
        Args:
            session_id: 会话 ID
        """
        if self._current_session == session_id:
            self._conversation_history.clear()
            self._clarification_count = 0
    
    def get_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        """获取会话历史
        
        Args:
            session_id: 会话 ID
            
        Returns:
            对话历史列表
        """
        if self._current_session != session_id:
            return []
        
        return self._conversation_history.copy()


# ============= 工厂函数 =============

def create_pm_agent(config: Optional[Dict[str, Any]] = None) -> PMAgent:
    """创建 PM Agent 实例
    
    Args:
        config: 配置字典
        
    Returns:
        PMAgent 实例
    """
    return PMAgent(config=config)
