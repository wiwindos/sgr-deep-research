"""LLM client abstractions for streaming chat completions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Type, TYPE_CHECKING

import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from sgr_deep_research.core.tools import BaseTool

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletion
    from openai.types.chat.chat_completion_message import ChatCompletionMessage
    from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall
    from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
    from sgr_deep_research.settings import MistralConfig, OpenAIConfig

try:  # pragma: no cover - optional dependency imported lazily
    from mistralai.extra import response_format_from_pydantic_model
    from mistralai.models import CompletionEvent, UsageInfo
    from mistralai.sdk import Mistral
    from mistralai.types import UNSET, UNSET_SENTINEL
except Exception:  # pragma: no cover - handled at runtime when mistralai is missing
    response_format_from_pydantic_model = None  # type: ignore
    CompletionEvent = None  # type: ignore
    UsageInfo = None  # type: ignore
    Mistral = None  # type: ignore
    UNSET = object()  # type: ignore
    UNSET_SENTINEL = object()  # type: ignore


StreamingCallback = Callable[[str], None]


@dataclass
class ToolCallResult:
    """Tool call output returned by the LLM."""

    name: str
    arguments: str
    parsed_arguments: BaseTool | None = None
    id: str | None = None


@dataclass
class LLMCompletionResult:
    """Final result of a streamed chat completion."""

    content: str | None
    parsed: Any | None
    tool_calls: list[ToolCallResult]
    finish_reason: str | None
    usage: Dict[str, int] | None


def _flatten_content(content: Any) -> str:
    """Convert completion content into a plain text string."""

    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
            else:
                text = getattr(item, "text", None)
                if isinstance(text, str):
                    parts.append(text)
                elif hasattr(item, "thinking"):
                    # Think chunks contain nested text chunks
                    for think_item in getattr(item, "thinking", []) or []:
                        nested_text = getattr(think_item, "text", None)
                        if isinstance(nested_text, str):
                            parts.append(nested_text)
        return "".join(parts)
    return str(content)


def _build_tool_call_result(
    *,
    name: str,
    arguments: Any,
    call_id: str | None,
    tool_classes: Dict[str, Type[BaseTool]] | None,
) -> ToolCallResult:
    arguments_str: str
    if isinstance(arguments, str):
        arguments_str = arguments
    else:
        arguments_str = json.dumps(arguments, ensure_ascii=False)

    parsed: BaseTool | None = None
    if tool_classes and name in tool_classes and arguments_str:
        try:
            parsed = tool_classes[name].model_validate_json(arguments_str)
        except ValidationError:
            parsed = None

    return ToolCallResult(name=name, arguments=arguments_str, parsed_arguments=parsed, id=call_id)


class OpenAIChatClient:
    """Adapter around the OpenAI async client."""

    def __init__(self, config: "OpenAIConfig"):
        client_kwargs: dict[str, Any] = {
            "api_key": config.api_key,
            "base_url": config.base_url,
        }
        if config.proxy and config.proxy.strip():
            client_kwargs["http_client"] = httpx.AsyncClient(proxy=config.proxy)
        self._client = AsyncOpenAI(**client_kwargs)

    async def stream_chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int | None,
        temperature: float | None,
        response_format: type[BaseModel] | None,
        tools: Any | None,
        tool_choice: Any | None,
        tool_classes: Dict[str, Type[BaseTool]] | None,
        on_text_chunk: StreamingCallback,
    ) -> LLMCompletionResult:
        stream = self._client.chat.completions.stream(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
            tools=tools,
            tool_choice=tool_choice,
        )

        async with stream as events:
            async for event in events:
                if getattr(event, "type", None) != "chunk":
                    continue
                chunk = getattr(event, "chunk", None)
                if chunk is None:
                    continue
                choices = getattr(chunk, "choices", [])
                if not choices:
                    continue
                delta = choices[0].delta
                text = _flatten_content(getattr(delta, "content", None))
                if text:
                    on_text_chunk(text)

        final_completion: "ChatCompletion" = await stream.get_final_completion()
        message: "ChatCompletionMessage" = final_completion.choices[0].message
        parsed = getattr(message, "parsed", None)
        content = _flatten_content(getattr(message, "content", None)) or None

        tool_calls: list[ToolCallResult] = []
        for tool_call in getattr(message, "tool_calls", []) or []:
            call_name = getattr(tool_call.function, "name", "")
            call_args = getattr(tool_call.function, "parsed_arguments", None)
            if call_args is not None and isinstance(call_args, BaseTool):
                result = ToolCallResult(
                    name=call_name,
                    arguments=call_args.model_dump_json(),
                    parsed_arguments=call_args,
                    id=getattr(tool_call, "id", None),
                )
            else:
                result = _build_tool_call_result(
                    name=call_name,
                    arguments=getattr(tool_call.function, "arguments", ""),
                    call_id=getattr(tool_call, "id", None),
                    tool_classes=tool_classes,
                )
            tool_calls.append(result)

        usage = None
        if getattr(final_completion, "usage", None) is not None:
            usage = final_completion.usage.model_dump()

        finish_reason = getattr(final_completion.choices[0], "finish_reason", None)

        return LLMCompletionResult(
            content=content,
            parsed=parsed,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )


class MistralChatClient:
    """Adapter around the official Mistral SDK."""

    def __init__(self, config: "MistralConfig"):
        if Mistral is None or response_format_from_pydantic_model is None:  # pragma: no cover - runtime guard
            raise RuntimeError(
                "The 'mistralai' package is required for the Mistral provider. Install it to enable this option."
            )

        async_client = None
        if config.proxy and config.proxy.strip():
            async_client = httpx.AsyncClient(proxies=config.proxy)

        self._client = Mistral(
            api_key=config.api_key,
            server_url=config.base_url,
            async_client=async_client,
        )

    async def stream_chat_completion(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_tokens: int | None,
        temperature: float | None,
        response_format: type[BaseModel] | None,
        tools: Any | None,
        tool_choice: Any | None,
        tool_classes: Dict[str, Type[BaseTool]] | None,
        on_text_chunk: StreamingCallback,
    ) -> LLMCompletionResult:
        response_format_payload = None
        if response_format is not None:
            response_format_payload = response_format_from_pydantic_model(response_format)

        tools_payload = None
        if tools is not None:
            tools_payload = []
            for tool in tools:
                if hasattr(tool, "model_dump"):
                    tools_payload.append(tool.model_dump())
                else:
                    tools_payload.append(tool)

        stream = await self._client.chat.stream_async(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format_payload,
            tools=tools_payload,
            tool_choice=tool_choice,
        )

        content_parts: list[str] = []
        tool_call_buffer: dict[int, dict[str, Any]] = {}
        finish_reason: str | None = None
        usage_dict: Dict[str, int] | None = None

        async with stream as events:
            async for event in events:  # type: ignore[union-attr]
                if not isinstance(event, CompletionEvent):
                    continue
                chunk = event.data
                if chunk.usage is not None:
                    usage_dict = chunk.usage.model_dump()

                for choice in chunk.choices:
                    delta = choice.delta
                    text = _flatten_content(getattr(delta, "content", None))
                    if text:
                        on_text_chunk(text)
                        content_parts.append(text)

                    delta_tool_calls = getattr(delta, "tool_calls", None)
                    if delta_tool_calls not in (None, UNSET, UNSET_SENTINEL):
                        for tool_call in delta_tool_calls:
                            index = getattr(tool_call, "index", 0) or 0
                            buffer = tool_call_buffer.setdefault(
                                index,
                                {
                                    "id": getattr(tool_call, "id", None),
                                    "name": "",
                                    "arguments": [],
                                },
                            )
                            name = getattr(getattr(tool_call, "function", None), "name", None)
                            if name:
                                buffer["name"] = name
                            arguments = getattr(getattr(tool_call, "function", None), "arguments", None)
                            if arguments not in (None, UNSET, UNSET_SENTINEL):
                                if isinstance(arguments, str):
                                    buffer["arguments"].append(arguments)
                                else:
                                    buffer["arguments"] = [json.dumps(arguments, ensure_ascii=False)]

                    fr = getattr(choice, "finish_reason", None)
                    if fr not in (None, UNSET, UNSET_SENTINEL):
                        finish_reason = str(fr)

        full_content = "".join(content_parts)
        parsed: Any | None = None
        if response_format is not None and full_content:
            try:
                parsed = response_format.model_validate_json(full_content)
            except ValidationError:
                parsed = None

        tool_calls: list[ToolCallResult] = []
        for buffer in tool_call_buffer.values():
            name = buffer.get("name")
            if not name:
                continue
            arguments_str = "".join(buffer.get("arguments", []))
            tool_calls.append(
                _build_tool_call_result(
                    name=name,
                    arguments=arguments_str,
                    call_id=buffer.get("id"),
                    tool_classes=tool_classes,
                )
            )

        return LLMCompletionResult(
            content=full_content or None,
            parsed=parsed,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage_dict,
        )
