"""Anthropic LLM provider implementation."""

import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from anthropic import AsyncAnthropic

from app.agents.llm.base import (
    BaseLLM,
    ChatMessage,
    LLMConfig,
    LLMProvider,
    LLMResponse,
)

logger = logging.getLogger(__name__)


class AnthropicLLM(BaseLLM):
    """Anthropic LLM provider."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self._client: Optional[AsyncAnthropic] = None

    def _get_client(self) -> AsyncAnthropic:
        """Get or create Anthropic client."""
        if self._client is None:
            self._client = AsyncAnthropic(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        return self._client

    def _convert_messages(
        self, messages: List[ChatMessage]
    ) -> tuple[Optional[str], List[Dict[str, str]]]:
        """Convert messages to Anthropic format.

        Anthropic uses a separate system prompt and messages list.
        """
        system_prompt = None
        anthropic_messages = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                anthropic_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        return system_prompt, anthropic_messages

    async def chat(
        self,
        messages: List[ChatMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send chat messages and get response."""
        client = self._get_client()

        system_prompt, anthropic_messages = self._convert_messages(messages)

        # Build request parameters
        params: Dict[str, Any] = {
            "model": self.config.model,
            "messages": anthropic_messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
        }
        if system_prompt:
            params["system"] = system_prompt
        params.update(kwargs)

        try:
            response = await client.messages.create(**params)

            # Extract text content
            text_content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text_content += block.text

            return LLMResponse(
                content=text_content,
                model=response.model,
                provider=LLMProvider.ANTHROPIC,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                },
                finish_reason=response.stop_reason or "end_turn",
            )
        except Exception as e:
            logger.error(f"Anthropic chat error: {e}")
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

        system_prompt, anthropic_messages = self._convert_messages(messages)

        # Build request parameters
        params: Dict[str, Any] = {
            "model": self.config.model,
            "messages": anthropic_messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
        }
        if system_prompt:
            params["system"] = system_prompt
        params.update(kwargs)

        try:
            async with client.messages.stream(**params) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Anthropic stream error: {e}")
            raise

    async def count_tokens(self, text: str) -> int:
        """Count tokens using Anthropic's token counting."""
        client = self._get_client()

        try:
            # Use Anthropic's count_tokens API if available
            response = await client.count_tokens(text)
            return response.num_tokens
        except Exception:
            # Fallback approximation
            logger.warning("Anthropic token counting failed, using approximation")
            return len(text) // 4