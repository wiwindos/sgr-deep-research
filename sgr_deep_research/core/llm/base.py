from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, AsyncContextManager, Mapping, Sequence, Type

from pydantic import BaseModel


@dataclass(slots=True)
class LLMToolCall:
    """Represents a tool call returned by the provider."""

    name: str
    arguments: str
    parsed: BaseModel | None = None
    id: str | None = None
    raw: Any | None = None


@dataclass(slots=True)
class LLMStreamDelta:
    """Incremental update from the provider stream."""

    content: str | None = None
    raw: Any | None = None


@dataclass(slots=True)
class LLMCompletionResult:
    """Final completion result returned by a provider."""

    content: str | None
    parsed: BaseModel | None
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    raw: Any | None = None


@dataclass(slots=True)
class LLMCompletionRequest:
    """Generic chat completion request for providers."""

    messages: Sequence[Mapping[str, Any]]
    response_model: Type[BaseModel] | None = None
    tools: Sequence[Any] | None = None
    tool_choice: Any | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    model: str | None = None
    stream: bool = True
    metadata: Mapping[str, Any] | None = None
    schema_name: str | None = None


class LLMCompletionStream(AsyncContextManager["LLMCompletionStream"], AsyncIterator[LLMStreamDelta], metaclass=abc.ABCMeta):
    """Asynchronous completion stream abstraction."""

    @abc.abstractmethod
    async def __aenter__(self) -> "LLMCompletionStream":
        raise NotImplementedError

    @abc.abstractmethod
    async def __aexit__(self, exc_type, exc, tb) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def __aiter__(self) -> "LLMCompletionStream":
        raise NotImplementedError

    @abc.abstractmethod
    async def __anext__(self) -> LLMStreamDelta:
        raise NotImplementedError

    @abc.abstractmethod
    async def get_final_response(self) -> LLMCompletionResult:
        raise NotImplementedError


class LLMError(RuntimeError):
    """Base error for LLM interaction failures."""


class StructuredOutputError(LLMError):
    """Raised when a structured output cannot be parsed or validated."""


class SchemaTooComplexError(LLMError):
    """Raised when schema compilation exceeds provider constraints."""


class LLMClient(abc.ABC):
    """Common interface for LLM providers."""

    provider: str
    default_model: str
    default_max_tokens: int | None
    default_temperature: float | None

    def __init__(self) -> None:
        self.provider = "unknown"
        self.default_model = ""
        self.default_max_tokens = None
        self.default_temperature = None

    @abc.abstractmethod
    def stream_chat_completion(self, request: LLMCompletionRequest) -> LLMCompletionStream:
        raise NotImplementedError

    def prepare_request(self, request: LLMCompletionRequest) -> LLMCompletionRequest:
        """Populate defaults for model, tokens and temperature."""

        if request.model is None:
            request.model = self.default_model
        if request.max_tokens is None:
            request.max_tokens = self.default_max_tokens
        if request.temperature is None:
            request.temperature = self.default_temperature
        return request
