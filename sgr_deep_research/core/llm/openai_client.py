from __future__ import annotations

import logging
from typing import Any

import httpx
from openai import AsyncOpenAI

from sgr_deep_research.core.llm.base import (
    LLMClient,
    LLMCompletionRequest,
    LLMCompletionResult,
    LLMCompletionStream,
    LLMStreamDelta,
    LLMToolCall,
)
from sgr_deep_research.core.llm.utils import coerce_content_to_str
from sgr_deep_research.settings import AppConfig


logger = logging.getLogger(__name__)


class OpenAICompletionStream(LLMCompletionStream):
    """Wrapper around OpenAI streaming interface providing generic events."""

    def __init__(self, manager, request: LLMCompletionRequest):
        self._manager = manager
        self._request = request
        self._stream = None
        self._aiter = None

    async def __aenter__(self) -> "OpenAICompletionStream":
        self._stream = await self._manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._manager is not None:
            await self._manager.__aexit__(exc_type, exc, tb)

    def __aiter__(self) -> "OpenAICompletionStream":
        if self._stream is None:
            raise RuntimeError("Stream not initialised")
        self._aiter = self._stream.__aiter__()
        return self

    async def __anext__(self) -> LLMStreamDelta:
        if self._aiter is None:
            raise StopAsyncIteration
        event = await self._aiter.__anext__()
        content = None
        if getattr(event, "type", "") == "chunk":
            delta = event.chunk.choices[0].delta
            content = coerce_content_to_str(getattr(delta, "content", None))
        return LLMStreamDelta(content=content, raw=event)

    async def get_final_response(self) -> LLMCompletionResult:
        final = await self._manager.get_final_completion()
        message = final.choices[0].message
        content = coerce_content_to_str(getattr(message, "content", None))
        parsed = getattr(message, "parsed", None)
        tool_calls: list[LLMToolCall] = []
        for call in getattr(message, "tool_calls", []) or []:
            function = getattr(call, "function", None)
            arguments = ""
            parsed_arguments = None
            if function is not None:
                arguments = getattr(function, "arguments", "")
                parsed_arguments = getattr(function, "parsed_arguments", None)
            tool_calls.append(
                LLMToolCall(
                    id=getattr(call, "id", None),
                    name=getattr(function, "name", ""),
                    arguments=arguments,
                    parsed=parsed_arguments,
                    raw=call,
                )
            )
        return LLMCompletionResult(content=content, parsed=parsed, tool_calls=tool_calls, raw=final)


class OpenAILLMClient(LLMClient):
    """LLM client wrapper for OpenAI compatible provider."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.provider = "openai"
        self.default_model = config.openai.model
        self.default_max_tokens = config.openai.max_tokens
        self.default_temperature = config.openai.temperature
        client_kwargs: dict[str, Any] = {
            "api_key": config.openai.api_key,
            "base_url": config.openai.base_url or "https://api.openai.com/v1",
        }
        if config.openai.proxy.strip():
            client_kwargs["http_client"] = httpx.AsyncClient(proxy=config.openai.proxy)
        self._client = AsyncOpenAI(**client_kwargs)

    def stream_chat_completion(self, request: LLMCompletionRequest) -> LLMCompletionStream:
        request = self.prepare_request(request)
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": list(request.messages),
        }
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.response_model is not None:
            kwargs["response_format"] = request.response_model
        if request.tools is not None:
            kwargs["tools"] = list(request.tools)
        if request.tool_choice is not None:
            kwargs["tool_choice"] = request.tool_choice
        if request.metadata is not None:
            kwargs["metadata"] = dict(request.metadata)
        manager = self._client.chat.completions.stream(**kwargs)
        return OpenAICompletionStream(manager, request)
