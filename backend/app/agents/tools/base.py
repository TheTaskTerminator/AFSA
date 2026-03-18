"""Base tool interface and common types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ToolCategory(str, Enum):
    """Tool categories."""

    FILE = "file"
    CODE = "code"
    DATABASE = "database"
    API = "api"
    SYSTEM = "system"


@dataclass
class ToolResult:
    """Result of tool execution."""

    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolParameter:
    """Tool parameter definition."""

    name: str
    type: str  # string, number, boolean, array, object
    description: str
    required: bool = True
    default: Optional[Any] = None
    enum: Optional[List[str]] = None


class BaseTool(ABC):
    """Abstract base class for agent tools.

    Tools provide agents with capabilities to interact with external systems.
    Each tool must implement execute() and provide its parameter schema.
    """

    name: str = "base_tool"
    description: str = "Base tool class"
    category: ToolCategory = ToolCategory.SYSTEM

    @property
    def parameters(self) -> List[ToolParameter]:
        """Get tool parameters.

        Returns:
            List of parameter definitions
        """
        return []

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool.

        Args:
            **kwargs: Tool parameters

        Returns:
            ToolResult with output or error
        """
        pass

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI function schema.

        Returns:
            OpenAI function definition
        """
        properties = {}
        required = []

        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def validate_parameters(self, **kwargs) -> Optional[str]:
        """Validate provided parameters.

        Args:
            **kwargs: Parameters to validate

        Returns:
            Error message if validation fails, None otherwise
        """
        param_names = {p.name for p in self.parameters}
        required_params = {p.name for p in self.parameters if p.required}

        # Check required parameters
        missing = required_params - set(kwargs.keys())
        if missing:
            return f"Missing required parameters: {missing}"

        # Check for unknown parameters
        unknown = set(kwargs.keys()) - param_names
        if unknown:
            return f"Unknown parameters: {unknown}"

        return None