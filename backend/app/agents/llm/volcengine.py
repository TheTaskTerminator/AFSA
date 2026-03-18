"""Volcengine (火山方舟) LLM provider implementation.

火山方舟 uses OpenAI-compatible API with custom base URL.
"""

import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from openai import AsyncOpenAI

from app.agents.llm.base import (
    BaseLLM,
    ChatMessage,
    LLMConfig,
    LLMProvider,
    LLMResponse,
)

logger = logging.getLogger(__name__)

# 火山方舟默认 base URL
VOLCENGINE_DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


class VolcengineLLM(BaseLLM):
    """Volcengine (火山方舟) LLM provider.

    火山方舟 provides OpenAI-compatible API endpoints.
    Model examples: doubao-pro-32k, doubao-pro-128k, etc.
    """

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        """Get or create Volcengine client."""
        if self._client is None:
            base_url = self.config.base_url or VOLCENGINE_DEFAULT_BASE_URL
            self._client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=base_url,
                timeout=self.config.timeout,
            )
        return self._client

    async def chat(
        self,
        messages: List[ChatMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send chat messages and get response."""
        client = self._get_client()

        # Convert messages to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # Build request parameters
        params: Dict[str, Any] = {
            "model": self.config.model,
            "messages": openai_messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
        }
        params.update(kwargs)

        try:
            response = await client.chat.completions.create(**params)

            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                provider=LLMProvider.VOLCENGINE,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                finish_reason=response.choices[0].finish_reason or "stop",
            )
        except Exception as e:
            logger.error(f"Volcengine chat error: {e}")
            raise

    async def chat_stream(
        self,
        messages: List[ChatMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream chat response."""
        client = self._get_client()

        # Convert messages to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # Build request parameters
        params: Dict[str, Any] = {
            "model": self.config.model,
            "messages": openai_messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": True,
        }
        params.update(kwargs)

        try:
            stream = await client.chat.completions.create(**params)
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Volcengine stream error: {e}")
            raise

    async def count_tokens(self, text: str) -> int:
        """Count tokens (approximation for Chinese text)."""
        # 火山方舟 models are optimized for Chinese
        # Approximate: ~1.5 characters per token for Chinese
        chinese_ratio = 1.5
        english_ratio = 4

        # Simple heuristic: check if text is mostly Chinese
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        total_chars = len(text)

        if chinese_chars > total_chars * 0.5:
            return int(total_chars / chinese_ratio)
        else:
            return total_chars // english_ratio