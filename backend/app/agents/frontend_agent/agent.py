"""Frontend Agent implementation for UI code generation."""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.agents.base import AgentResponse, AgentType, BaseAgent, TaskCard
from app.agents.llm import BaseLLM, ChatMessage, get_llm
from app.agents.frontend_agent.prompts import (
    CODE_GENERATION_PROMPT,
    FRONTEND_SYSTEM_PROMPT,
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

logger = logging.getLogger(__name__)


@dataclass
class GenerationSession:
    """Session for code generation."""

    session_id: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    generated_files: List[GeneratedFile] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    is_complete: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class FrontendAgent(BaseAgent):
    """Frontend Development Agent for UI code generation.

    The Frontend Agent is responsible for:
    1. Understanding UI requirements
    2. Generating React + TypeScript components
    3. Creating Zustand stores for state management
    4. Submitting code to sandbox for validation

    Attributes:
        agent_type: Always AgentType.FRONTEND
        name: Agent name for identification
        llm: LLM instance for code generation
        tools: Tool instances for code operations
    """

    agent_type = AgentType.FRONTEND
    name = "Frontend Agent"

    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize Frontend Agent.

        Args:
            llm: LLM instance (will use default if not provided)
            config: Agent configuration
        """
        self._llm = llm
        self._config = config or {}
        self._sessions: Dict[str, GenerationSession] = {}

        # Tools will be initialized when LLM is available
        self._generation_tool: Optional[CodeGenerationTool] = None
        self._validation_tool: Optional[CodeValidationTool] = None
        self._sandbox_tool: Optional[SandboxSubmitTool] = None

    @property
    def llm(self) -> BaseLLM:
        """Get LLM instance."""
        if self._llm is None:
            self._llm = get_llm()
        return self._llm

    def _ensure_tools(self) -> None:
        """Ensure tools are initialized."""
        if self._generation_tool is None:
            self._generation_tool = CodeGenerationTool(self.llm)
        if self._validation_tool is None:
            self._validation_tool = CodeValidationTool(self.llm)
        if self._sandbox_tool is None:
            sandbox_url = self._config.get("sandbox_url", "http://localhost:8080")
            self._sandbox_tool = SandboxSubmitTool(sandbox_url)

    def _get_or_create_session(self, session_id: str) -> GenerationSession:
        """Get existing session or create new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = GenerationSession(session_id=session_id)
        return self._sessions[session_id]

    async def process_message(
        self,
        session_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        """Process a user message for code generation.

        Args:
            session_id: Session identifier
            message: User message describing UI requirements
            context: Additional context (existing code, design specs, etc.)

        Returns:
            AgentResponse with generated code or clarification questions
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

        try:
            # Detect what kind of component to generate
            component_type = detect_component_type(message)
            component_name = extract_component_name(message)

            # Build messages for LLM
            llm_messages = self._build_llm_messages(session, message)

            # Get LLM response
            response = await self.llm.chat(llm_messages, temperature=0.3)
            content = response.content

            # Parse response for code generation or clarification
            parsed = self._parse_response(content)

            # Add assistant message to history
            session.messages.append({
                "role": "assistant",
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
            })
            session.updated_at = datetime.utcnow()

            if parsed.get("type") == "clarification":
                return AgentResponse(
                    success=True,
                    content="我需要澄清一些细节：",
                    clarification_questions=parsed.get("questions", []),
                    metadata={"session_id": session_id, "type": "clarification"},
                )

            elif parsed.get("type") == "code_generation":
                files_data = parsed.get("files", [])
                generated_files = [
                    GeneratedFile(
                        path=f.get("path", f"src/components/{component_name}.tsx"),
                        content=f.get("content", ""),
                        description=f.get("description", ""),
                        language=f.get("language", "typescript"),
                    )
                    for f in files_data
                ]

                session.generated_files.extend(generated_files)

                # Validate generated code
                validation_results = []
                for file in generated_files:
                    if file.language == "typescript":
                        validation = await self._validation_tool.validate_typescript(file.content)
                        validation_results.append({
                            "file": file.path,
                            "is_valid": validation.is_valid,
                            "errors": validation.errors,
                            "warnings": validation.warnings,
                        })

                return AgentResponse(
                    success=True,
                    content=f"已生成 {len(generated_files)} 个文件",
                    metadata={
                        "session_id": session_id,
                        "type": "code_generation",
                        "files": [{"path": f.path, "description": f.description} for f in generated_files],
                        "dependencies": parsed.get("dependencies", []),
                        "validation": validation_results,
                    },
                )

            else:
                # Regular response
                return AgentResponse(
                    success=True,
                    content=content,
                    metadata={"session_id": session_id},
                )

        except Exception as e:
            logger.error(f"Frontend Agent error: {e}")
            return AgentResponse(
                success=False,
                content=f"代码生成时出错：{str(e)}",
                metadata={"error": str(e), "session_id": session_id},
            )

    async def generate_task_card(self, session_id: str) -> Optional[TaskCard]:
        """Generate a structured task card from the conversation.

        Args:
            session_id: Session identifier

        Returns:
            TaskCard if successfully generated, None otherwise
        """
        session = self._sessions.get(session_id)

        if not session or not session.messages:
            return None

        # Create task card from the generation session
        task_card = TaskCard(
            id=str(uuid.uuid4()),
            type="feature",
            priority="medium",
            description="UI 组件生成任务",
            structured_requirements=[
                {
                    "id": f"req-{i+1}",
                    "description": msg.get("content", ""),
                    "acceptance_criteria": "组件正常渲染，无 TypeScript 错误",
                }
                for i, msg in enumerate(session.messages)
                if msg.get("role") == "user"
            ],
            constraints={
                "technology_stack": ["React", "TypeScript", "Tailwind CSS", "shadcn/ui"],
            },
        )

        return task_card

    async def execute(self, task_card: TaskCard) -> AgentResponse:
        """Execute code generation for the task.

        Args:
            task_card: Task card with UI requirements

        Returns:
            AgentResponse with generated code
        """
        self._ensure_tools()

        try:
            # Extract requirements from task card
            description = task_card.description
            requirements = task_card.structured_requirements
            constraints = task_card.constraints

            # Generate code
            result = await self._generation_tool.generate_component(
                description=description,
                component_type=detect_component_type(description),
                constraints=constraints,
            )

            if result.errors:
                return AgentResponse(
                    success=False,
                    content="代码生成失败",
                    metadata={"errors": result.errors},
                )

            # Validate generated code
            validation_results = []
            for file in result.files:
                if file.language == "typescript":
                    validation = await self._validation_tool.validate_typescript(file.content)
                    validation_results.append({
                        "file": file.path,
                        "is_valid": validation.is_valid,
                        "errors": validation.errors,
                        "warnings": validation.warnings,
                        "suggestions": validation.suggestions,
                    })

            # Submit to sandbox if configured
            sandbox_result = None
            if self._config.get("auto_submit_sandbox", False):
                sandbox_result = await self._sandbox_tool.submit_code(
                    files=result.files,
                    task_id=task_card.id,
                )

            return AgentResponse(
                success=True,
                content=f"成功生成 {len(result.files)} 个文件",
                metadata={
                    "files": [{"path": f.path, "content": f.content} for f in result.files],
                    "dependencies": result.dependencies,
                    "validation": validation_results,
                    "sandbox": sandbox_result,
                },
                task_card=task_card,
            )

        except Exception as e:
            logger.error(f"Frontend Agent execution error: {e}")
            return AgentResponse(
                success=False,
                content=f"执行失败：{str(e)}",
                metadata={"error": str(e)},
            )

    def _build_llm_messages(
        self,
        session: GenerationSession,
        current_message: str,
    ) -> List[ChatMessage]:
        """Build message list for LLM."""
        messages = [ChatMessage(role="system", content=get_system_prompt())]

        # Add existing code context if available
        if session.generated_files:
            existing_code = "\n\n".join(
                f"// {f.path}\n{f.content}"
                for f in session.generated_files[-3:]  # Last 3 files
            )
            messages.append(ChatMessage(
                role="system",
                content=f"已生成的代码：\n{existing_code}",
            ))

        # Add conversation history (limit to last 8 messages)
        for msg in session.messages[-8:]:
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
        import re

        # Try to find JSON in the response
        json_pattern = r"```json\s*([\s\S]*?)\s*```"
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

    def get_generated_files(self, session_id: str) -> List[GeneratedFile]:
        """Get all generated files for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of generated files
        """
        session = self._sessions.get(session_id)
        if not session:
            return []
        return session.generated_files

    def clear_session(self, session_id: str) -> bool:
        """Clear a session from memory."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False