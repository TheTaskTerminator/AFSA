"""OpenAI LLM provider implementation."""

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


class OpenAILLM(BaseLLM):
    """OpenAI LLM provider."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client: Optional[AsyncOpenAI] = None

    def _get_client(self) -> AsyncOpenAI:
        """Get or create OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
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
                provider=LLMProvider.OPENAI,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                finish_reason=response.choices[0].finish_reason or "stop",
            )
        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
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
            logger.error(f"OpenAI stream error: {e}")
            raise

    async def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken."""
        try:
            import tiktoken

            encoding = tiktoken.encoding_for_model(self.config.model)
            return len(encoding.encode(text))
        except ImportError:
            logger.warning("tiktoken not installed, using approximation")
            # Approximate: ~4 characters per token for English
            return len(text) // 4
        except Exception:
            # Fallback for unknown models
            return len(text) // 4