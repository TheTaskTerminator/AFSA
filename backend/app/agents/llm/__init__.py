"""LLM provider abstraction layer.

This module provides a unified interface for multiple LLM providers:
- OpenAI
- Anthropic
- 火山方舟 (Volcengine)
- 阿里云百炼 (Alibaba Cloud)
- GLM (智谱 AI)

Usage:
    from app.agents.llm import get_llm, LLMProvider, ChatMessage

    # Get LLM instance from config
    llm = get_llm()

    # Or create with specific config
    from app.agents.llm import LLMConfig, create_llm
    config = LLMConfig(
        provider=LLMProvider.OPENAI,
        api_key="your-api-key",
        model="gpt-4-turbo",
    )
    llm = create_llm(config)

    # Use the LLM
    messages = [ChatMessage(role="user", content="Hello!")]
    response = await llm.chat(messages)
"""

import logging
from typing import Optional

from app.config import settings

from .base import (
    BaseLLM,
    ChatMessage,
    LLMConfig,
    LLMProvider,
    LLMResponse,
)
from .openai import OpenAILLM
from .anthropic import AnthropicLLM
from .volcengine import VolcengineLLM
from .aliyun import AliyunLLM
from .glm import GLMLLM

logger = logging.getLogger(__name__)

__all__ = [
    # Base classes
    "BaseLLM",
    "ChatMessage",
    "LLMConfig",
    "LLMProvider",
    "LLMResponse",
    # Provider implementations
    "OpenAILLM",
    "AnthropicLLM",
    "VolcengineLLM",
    "AliyunLLM",
    "GLMLLM",
    # Factory functions
    "create_llm",
    "get_llm",
]


def create_llm(config: LLMConfig) -> BaseLLM:
    """Create an LLM instance based on configuration.

    Args:
        config: LLM configuration

    Returns:
        LLM instance for the specified provider

    Raises:
        ValueError: If provider is not supported
    """
    providers = {
        LLMProvider.OPENAI: OpenAILLM,
        LLMProvider.ANTHROPIC: AnthropicLLM,
        LLMProvider.VOLCENGINE: VolcengineLLM,
        LLMProvider.ALIYUN: AliyunLLM,
        LLMProvider.GLM: GLMLLM,
    }

    llm_class = providers.get(config.provider)
    if llm_class is None:
        raise ValueError(f"Unsupported LLM provider: {config.provider}")

    return llm_class(config)


def get_llm() -> BaseLLM:
    """Get LLM instance from application settings.

    Returns:
        LLM instance configured from settings
    """
    provider = LLMProvider(settings.llm_provider)

    # Build config based on provider
    config_map = {
        LLMProvider.OPENAI: lambda: LLMConfig(
            provider=LLMProvider.OPENAI,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url,
        ),
        LLMProvider.ANTHROPIC: lambda: LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            base_url=settings.anthropic_base_url,
        ),
        LLMProvider.VOLCENGINE: lambda: LLMConfig(
            provider=LLMProvider.VOLCENGINE,
            api_key=settings.volcengine_api_key,
            model=settings.volcengine_model,
            base_url=settings.volcengine_base_url,
        ),
        LLMProvider.ALIYUN: lambda: LLMConfig(
            provider=LLMProvider.ALIYUN,
            api_key=settings.aliyun_api_key,
            model=settings.aliyun_model,
            base_url=settings.aliyun_base_url,
        ),
        LLMProvider.GLM: lambda: LLMConfig(
            provider=LLMProvider.GLM,
            api_key=settings.glm_api_key,
            model=settings.glm_model,
            base_url=settings.glm_base_url,
        ),
    }

    config_factory = config_map.get(provider)
    if config_factory is None:
        raise ValueError(f"Unsupported LLM provider: {provider}")

    return create_llm(config_factory())


# Global LLM instance (lazy initialization)
_llm_instance: Optional[BaseLLM] = None


async def get_llm_instance() -> BaseLLM:
    """Get or create global LLM instance.

    This function provides a singleton pattern for LLM instance.

    Returns:
        LLM instance
    """
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = get_llm()
    return _llm_instance