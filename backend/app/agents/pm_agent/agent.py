"""PM Agent implementation for requirement analysis and task management."""

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.agents.base import AgentResponse, AgentType, BaseAgent, TaskCard
from app.agents.llm import BaseLLM, ChatMessage, get_llm
from app.agents.pm_agent.prompts import (
    TASK_CARD_GENERATION_PROMPT,
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

logger = logging.getLogger(__name__)


@dataclass
class ConversationState:
    """State of a conversation session."""

    session_id: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    clarification_count: int = 0
    max_clarifications: int = 3
    is_complete: bool = False
    task_card: Optional[TaskCard] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class PMAgent(BaseAgent):
    """Product Manager Agent for requirement analysis and task management.

    The PM Agent is responsible for:
    1. Understanding user requirements
    2. Conducting clarification dialogues
    3. Generating structured task cards
    4. Dispatching tasks to appropriate agents

    Attributes:
        agent_type: Always AgentType.PM
        name: Agent name for identification
        llm: LLM instance for conversation
        tools: Tool instances for analysis
    """

    agent_type = AgentType.PM
    name = "PM Agent"

    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize PM Agent.

        Args:
            llm: LLM instance (will use default if not provided)
            config: Agent configuration
        """
        self._llm = llm
        self._config = config or {}
        self._sessions: Dict[str, ConversationState] = {}

        # Tools will be initialized when LLM is available
        self._clarification_tool: Optional[ClarificationTool] = None
        self._task_analysis_tool: Optional[TaskAnalysisTool] = None
        self._compression_tool: Optional[ContextCompressionTool] = None

    @property
    def llm(self) -> BaseLLM:
        """Get LLM instance."""
        if self._llm is None:
            self._llm = get_llm()
        return self._llm

    def _ensure_tools(self) -> None:
        """Ensure tools are initialized."""
        if self._clarification_tool is None:
            self._clarification_tool = ClarificationTool(self.llm)
        if self._task_analysis_tool is None:
            self._task_analysis_tool = TaskAnalysisTool(self.llm)
        if self._compression_tool is None:
            self._compression_tool = ContextCompressionTool(self.llm)

    def _get_or_create_session(self, session_id: str) -> ConversationState:
        """Get existing session or create new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationState(session_id=session_id)
        return self._sessions[session_id]

    async def process_message(
        self,
        session_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Process a user message.

        Args:
            session_id: Session identifier
            message: User message
            context: Additional context

        Returns:
            AgentResponse with content and optional clarification questions
        """
        self._ensure_tools()
        session = self._get_or_create_session(session_id)

        # Update context if provided
        if context:
            session.context.update(context)

        # Add user message to history
        session.messages.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Check if context needs compression
        if await self._compression_tool.should_compress(session.messages):
            compressed = await self._compression_tool.compress_context(session.messages)
            session.context["compressed_summary"] = compressed
            # Keep only recent messages after compression
            session.messages = session.messages[-4:]

        try:
            # Build messages for LLM
            llm_messages = self._build_llm_messages(session, message)

            # Get LLM response
            response = await self.llm.chat(llm_messages, temperature=0.7)
            content = response.content

            # Parse response for clarification or task card
            parsed = self._parse_response(content)

            # Add assistant message to history
            session.messages.append({
                "role": "assistant",
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
            })
            session.updated_at = datetime.utcnow()

            if parsed.get("type") == "clarification":
                session.clarification_count += 1

                return AgentResponse(
                    success=True,
                    content="我需要澄清一些问题：",
                    clarification_questions=parsed.get("questions", []),
                    metadata={"session_id": session_id, "type": "clarification"},
                )

            elif parsed.get("type") == "task_card":
                task_data = parsed.get("task", {})
                session.task_card = TaskCard(
                    id=task_data.get("id", str(uuid.uuid4())),
                    type=task_data.get("type", "feature"),
                    priority=task_data.get("priority", "medium"),
                    description=task_data.get("description", ""),
                    structured_requirements=task_data.get("structured_requirements", []),
                    constraints=task_data.get("constraints", {}),
                )
                session.is_complete = True

                return AgentResponse(
                    success=True,
                    content="任务卡片已生成！",
                    task_card=session.task_card,
                    metadata={"session_id": session_id, "type": "task_card"},
                )

            else:
                # Regular response
                return AgentResponse(
                    success=True,
                    content=content,
                    metadata={"session_id": session_id},
                )

        except Exception as e:
            logger.error(f"PM Agent error: {e}")
            return AgentResponse(
                success=False,
                content=f"处理消息时出错：{str(e)}",
                metadata={"error": str(e), "session_id": session_id},
            )

    async def generate_task_card(self, session_id: str) -> Optional[TaskCard]:
        """Generate a structured task card from the conversation.

        Args:
            session_id: Session identifier

        Returns:
            TaskCard if successfully generated, None otherwise
        """
        self._ensure_tools()
        session = self._sessions.get(session_id)

        if not session or not session.messages:
            return None

        # If task card already exists, return it
        if session.task_card:
            return session.task_card

        try:
            # Analyze the conversation
            analysis = await self._task_analysis_tool.analyze_task(
                description=session.context.get("original_request", ""),
                conversation_history=session.messages,
            )

            # Create task card from analysis
            task_card = TaskCard(
                id=str(uuid.uuid4()),
                type=analysis.task_type,
                priority=analysis.priority,
                description=analysis.description,
                structured_requirements=analysis.requirements,
                constraints=analysis.constraints,
            )

            session.task_card = task_card
            session.is_complete = True

            return task_card

        except Exception as e:
            logger.error(f"Task card generation error: {e}")
            return None

    async def execute(self, task_card: TaskCard) -> AgentResponse:
        """Execute the PM Agent workflow.

        For PM Agent, execution means finalizing the task card
        and preparing for dispatch.

        Args:
            task_card: Task card to execute

        Returns:
            AgentResponse with execution result
        """
        # PM Agent doesn't execute in the traditional sense
        # It prepares task cards for other agents
        return AgentResponse(
            success=True,
            content=f"任务卡片已准备就绪，类型：{task_card.type}，优先级：{task_card.priority}",
            task_card=task_card,
            metadata={"status": "ready_for_dispatch"},
        )

    def _build_llm_messages(
        self,
        session: ConversationState,
        current_message: str,
    ) -> List[ChatMessage]:
        """Build message list for LLM."""
        messages = [ChatMessage(role="system", content=get_system_prompt())]

        # Add compressed summary if available
        if "compressed_summary" in session.context:
            summary = session.context["compressed_summary"]
            messages.append(ChatMessage(
                role="system",
                content=f"之前的对话摘要：{summary.get('summary', '')}",
            ))

        # Add conversation history (limit to last 10 messages)
        for msg in session.messages[-10:]:
            messages.append(ChatMessage(
                role=msg["role"],
                content=msg["content"],
            ))

        return messages

    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Parse LLM response for structured output.

        Args:
            content: LLM response content

        Returns:
            Parsed dictionary with type and data
        """
        # Try to find JSON in the response
        json_pattern = r'```json\s*([\s\S]*?)\s*```'
        matches = re.findall(json_pattern, content)

        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                pass

        # Try direct JSON parse
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # No structured output found
        return {"type": "response", "content": content}

    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current state of a session."""
        session = self._sessions.get(session_id)
        if not session:
            return None

        return {
            "session_id": session.session_id,
            "message_count": len(session.messages),
            "clarification_count": session.clarification_count,
            "is_complete": session.is_complete,
            "has_task_card": session.task_card is not None,
        }

    def clear_session(self, session_id: str) -> bool:
        """Clear a session from memory."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False