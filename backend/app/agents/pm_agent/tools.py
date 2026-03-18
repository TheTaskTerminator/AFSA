"""PM Agent tools for requirement analysis and task management."""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.agents.llm import BaseLLM, ChatMessage

logger = logging.getLogger(__name__)


@dataclass
class ClarificationResult:
    """Result of clarification analysis."""

    needs_clarification: bool
    questions: List[Dict[str, Any]]
    confidence: float  # 0.0 - 1.0


@dataclass
class TaskAnalysisResult:
    """Result of task analysis."""

    task_type: str  # feature, bugfix, config
    priority: str  # high, medium, low
    description: str
    requirements: List[Dict[str, Any]]
    constraints: Dict[str, Any]
    estimated_complexity: str  # simple, medium, complex


class ClarificationTool:
    """Tool for generating and managing clarification questions."""

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def analyze_needs_clarification(
        self,
        description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ClarificationResult:
        """Analyze if the description needs clarification.

        Args:
            description: User's requirement description
            context: Additional context

        Returns:
            ClarificationResult with questions if needed
        """
        prompt = f"""分析以下需求描述，判断是否需要澄清问题。

需求描述：
{description}

上下文：
{json.dumps(context, ensure_ascii=False) if context else '无'}

请输出 JSON 格式：
{{
  "needs_clarification": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "判断理由",
  "unclear_points": ["不清楚的点1", "不清楚的点2"]
}}
"""
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await self.llm.chat(messages, temperature=0.3)
            result = json.loads(response.content)

            return ClarificationResult(
                needs_clarification=result.get("needs_clarification", True),
                questions=[{"question": p} for p in result.get("unclear_points", [])],
                confidence=result.get("confidence", 0.5),
            )
        except Exception as e:
            logger.error(f"Clarification analysis error: {e}")
            return ClarificationResult(
                needs_clarification=True,
                questions=[{"question": "请提供更多关于您需求的细节"}],
                confidence=0.0,
            )

    async def generate_questions(
        self,
        description: str,
        unclear_points: List[str],
        count: int = 3,
    ) -> List[Dict[str, Any]]:
        """Generate clarification questions.

        Args:
            description: Original description
            unclear_points: Points that need clarification
            count: Number of questions to generate

        Returns:
            List of question dictionaries
        """
        prompt = f"""基于以下需求描述和需要澄清的点，生成 {count} 个澄清问题。

需求描述：
{description}

需要澄清的点：
{chr(10).join(f'- {p}' for p in unclear_points)}

要求：
1. 问题简洁明了
2. 每个问题针对一个具体方面
3. 提供可能的选项（如果有）

请输出 JSON 数组格式：
[
  {{
    "id": "q1",
    "question": "问题内容",
    "options": ["选项A", "选项B"],
    "reason": "为什么要问这个问题"
  }}
]
"""
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await self.llm.chat(messages, temperature=0.5)
            questions = json.loads(response.content)
            return questions[:count]
        except Exception as e:
            logger.error(f"Question generation error: {e}")
            return [{"id": f"q{i+1}", "question": p} for i, p in enumerate(unclear_points[:count])]


class TaskAnalysisTool:
    """Tool for analyzing and structuring tasks."""

    def __init__(self, llm: BaseLLM):
        self.llm = llm

    async def analyze_task(
        self,
        description: str,
        conversation_history: List[Dict[str, str]],
    ) -> TaskAnalysisResult:
        """Analyze task from description and conversation.

        Args:
            description: Task description
            conversation_history: Previous conversation messages

        Returns:
            TaskAnalysisResult with structured task information
        """
        history_text = "\n".join(
            f"{msg['role']}: {msg['content']}"
            for msg in conversation_history[-10:]  # Last 10 messages
        )

        prompt = f"""分析以下需求，提取结构化的任务信息。

需求描述：
{description}

对话历史：
{history_text}

请输出 JSON 格式：
{{
  "task_type": "feature|bugfix|config",
  "priority": "high|medium|low",
  "description": "简洁的任务描述",
  "requirements": [
    {{
      "id": "req-1",
      "description": "需求描述",
      "acceptance_criteria": "验收标准"
    }}
  ],
  "constraints": {{
    "timeout_seconds": 300,
    "technology_stack": ["Python", "FastAPI"],
    "other_constraints": []
  }},
  "estimated_complexity": "simple|medium|complex"
}}
"""
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await self.llm.chat(messages, temperature=0.3)
            result = json.loads(response.content)

            return TaskAnalysisResult(
                task_type=result.get("task_type", "feature"),
                priority=result.get("priority", "medium"),
                description=result.get("description", description),
                requirements=result.get("requirements", []),
                constraints=result.get("constraints", {}),
                estimated_complexity=result.get("estimated_complexity", "medium"),
            )
        except Exception as e:
            logger.error(f"Task analysis error: {e}")
            return TaskAnalysisResult(
                task_type="feature",
                priority="medium",
                description=description,
                requirements=[{"id": "req-1", "description": description, "acceptance_criteria": "功能正常运行"}],
                constraints={"timeout_seconds": 300},
                estimated_complexity="medium",
            )

    async def split_task(
        self,
        task_analysis: TaskAnalysisResult,
        max_subtasks: int = 5,
    ) -> List[Dict[str, Any]]:
        """Split a complex task into subtasks.

        Args:
            task_analysis: Analyzed task information
            max_subtasks: Maximum number of subtasks

        Returns:
            List of subtask dictionaries
        """
        if task_analysis.estimated_complexity == "simple":
            return [task_analysis.requirements]

        prompt = f"""将以下复杂任务拆分为 {max_subtasks} 个以内的子任务。

任务类型：{task_analysis.task_type}
任务描述：{task_analysis.description}
需求列表：
{json.dumps(task_analysis.requirements, ensure_ascii=False, indent=2)}
约束条件：
{json.dumps(task_analysis.constraints, ensure_ascii=False, indent=2)}

要求：
1. 每个子任务应独立可执行
2. 子任务之间应有清晰的依赖关系
3. 每个子任务预计 1-4 小时完成

请输出 JSON 数组格式：
[
  {{
    "id": "subtask-1",
    "description": "子任务描述",
    "requirements": ["需求ID列表"],
    "dependencies": ["依赖的子任务ID"],
    "estimated_hours": 2,
    "assigned_agent": "frontend|backend"
  }}
]
"""
        messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await self.llm.chat(messages, temperature=0.4)
            subtasks = json.loads(response.content)
            return subtasks[:max_subtasks]
        except Exception as e:
            logger.error(f"Task splitting error: {e}")
            return [
                {
                    "id": f"subtask-{i+1}",
                    "description": req.get("description", ""),
                    "requirements": [req.get("id", f"req-{i+1}")],
                    "dependencies": [],
                    "estimated_hours": 2,
                    "assigned_agent": "backend",
                }
                for i, req in enumerate(task_analysis.requirements[:max_subtasks])
            ]


class ContextCompressionTool:
    """Tool for compressing conversation context."""

    def __init__(self, llm: BaseLLM, max_tokens: int = 4000):
        self.llm = llm
        self.max_tokens = max_tokens

    async def should_compress(
        self,
        messages: List[Dict[str, str]],
    ) -> bool:
        """Check if context should be compressed.

        Args:
            messages: Conversation messages

        Returns:
            True if compression is needed
        """
        total_length = sum(len(msg.get("content", "")) for msg in messages)
        # Approximate token count (roughly 4 chars per token)
        estimated_tokens = total_length // 4
        return estimated_tokens > self.max_tokens

    async def compress_context(
        self,
        messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Compress conversation context into summary.

        Args:
            messages: Conversation messages

        Returns:
            Compressed context with summary
        """
        history_text = "\n".join(
            f"{msg['role']}: {msg['content']}"
            for msg in messages
        )

        prompt = f"""总结以下对话内容，提取关键信息。

对话内容：
{history_text}

请输出 JSON 格式：
{{
  "summary": "对话摘要（100字以内）",
  "key_decisions": ["关键决策1", "关键决策2"],
  "requirements": ["已确认的需求1", "已确认的需求2"],
  "open_questions": ["待解决的问题1"],
  "action_items": ["下一步行动1"]
}}
"""
        chat_messages = [ChatMessage(role="user", content=prompt)]

        try:
            response = await self.llm.chat(chat_messages, temperature=0.3)
            result = json.loads(response.content)

            return {
                "compressed": True,
                "original_message_count": len(messages),
                **result,
            }
        except Exception as e:
            logger.error(f"Context compression error: {e}")
            return {
                "compressed": False,
                "original_message_count": len(messages),
                "summary": "压缩失败，保留原始上下文",
            }