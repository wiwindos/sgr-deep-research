from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Mapping

from mistralai import Mistral
from mistralai.extra.struct_chat import ParsedChatCompletionResponse
from mistralai.models.chatcompletionresponse import ChatCompletionResponse
from mistralai.models.completionevent import CompletionEvent
from mistralai.utils.eventstreaming import EventStreamAsync
from pydantic import BaseModel, ValidationError

from sgr_deep_research.core.llm.base import (
    LLMClient,
    LLMCompletionRequest,
    LLMCompletionResult,
    LLMCompletionStream,
    LLMStreamDelta,
    SchemaTooComplexError,
    StructuredOutputError,
)
from sgr_deep_research.core.llm.schema_compiler import CompiledSchema, SchemaCompiler
from sgr_deep_research.core.llm.utils import coerce_content_to_str, iter_json_chunks, soft_json_parse
from sgr_deep_research.settings import AppConfig


logger = logging.getLogger(__name__)


class MistralLiveStream(LLMCompletionStream):
    """Streaming wrapper for non-structured Mistral responses."""

    def __init__(self, stream: EventStreamAsync[CompletionEvent]):
        self._stream_ctx = stream
        self._stream: EventStreamAsync[CompletionEvent] | None = None
        self._aiter = None
        self._buffer: list[str] = []

    async def __aenter__(self) -> "MistralLiveStream":
        self._stream = await self._stream_ctx.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._stream_ctx is not None:
            await self._stream_ctx.__aexit__(exc_type, exc, tb)

    def __aiter__(self) -> "MistralLiveStream":
        if self._stream is None:
            raise RuntimeError("Stream has not been initialised")
        self._aiter = self._stream.__aiter__()
        return self

    async def __anext__(self) -> LLMStreamDelta:
        if self._aiter is None:
            raise StopAsyncIteration
        event = await self._aiter.__anext__()
        chunk_text = None
        if getattr(event, "data", None) is not None:
            choices = getattr(event.data, "choices", None) or []
            if choices:
                delta = choices[0].delta
                chunk_text = coerce_content_to_str(getattr(delta, "content", None))
                if chunk_text:
                    self._buffer.append(chunk_text)
        return LLMStreamDelta(content=chunk_text, raw=event)

    async def get_final_response(self) -> LLMCompletionResult:
        content = "".join(self._buffer) if self._buffer else None
        return LLMCompletionResult(content=content, parsed=None, raw=None)


class MistralStructuredStream(LLMCompletionStream):
    """Stream wrapper that emulates streaming from a completed JSON payload."""

    def __init__(self, completion_coro):
        self._completion_coro = completion_coro
        self._result: LLMCompletionResult | None = None
        self._chunks: list[str] = []
        self._iter: Iterable[str] | None = None

    async def __aenter__(self) -> "MistralStructuredStream":
        self._result, self._chunks = await self._completion_coro()
        self._iter = iter(self._chunks)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    def __aiter__(self) -> "MistralStructuredStream":
        if self._iter is None:
            raise RuntimeError("Stream has not been initialised")
        return self

    async def __anext__(self) -> LLMStreamDelta:
        assert self._iter is not None
        try:
            chunk = next(self._iter)
        except StopIteration:
            raise StopAsyncIteration
        return LLMStreamDelta(content=chunk)

    async def get_final_response(self) -> LLMCompletionResult:
        if self._result is None:
            raise StructuredOutputError("Structured response not available")
        return self._result


class MistralLLMClient(LLMClient):
    """Mistral LLM client with Custom Structured Output support."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.provider = "mistral"
        self.default_model = config.mistral.model
        self.default_max_tokens = config.mistral.max_tokens
        self.default_temperature = config.mistral.temperature
        self._so_mode = (config.mistral.so_mode or "native").lower()
        self._strict = config.mistral.strict
        self._compiler = SchemaCompiler(allow_additional_properties=config.mistral.allow_additional_properties)
        self._client = Mistral(api_key=config.mistral.api_key, server_url=config.mistral.base_url or None)
        self._chat = self._client.chat

    def stream_chat_completion(self, request: LLMCompletionRequest) -> LLMCompletionStream:
        request = self.prepare_request(request)
        if request.response_model is None:
            kwargs = self._build_request_kwargs(request)
            stream = self._chat.stream_async(**kwargs)
            return MistralLiveStream(stream)
        return MistralStructuredStream(lambda: self._complete_structured(request))

    # Structured output helpers ---------------------------------------

    def _build_request_kwargs(self, request: LLMCompletionRequest) -> dict[str, Any]:
        messages = []
        for message in request.messages:
            payload = {key: value for key, value in dict(message).items() if value is not None}
            messages.append(payload)
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
        }
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        return kwargs

    def _log_stage(
        self,
        request: LLMCompletionRequest,
        stage: str,
        level: int,
        message: str,
        **extra: Any,
    ) -> None:
        payload = {
            "provider": self.provider,
            "model": request.model,
            "so_mode": self._so_mode,
            "schema_name": extra.pop("schema_name", None),
            "retry_stage": stage,
        }
        payload.update(extra)
        logger.log(level, message, extra=payload)

    async def _complete_structured(self, request: LLMCompletionRequest) -> tuple[LLMCompletionResult, list[str]]:
        assert request.response_model is not None
        schema_name = request.schema_name or request.response_model.__name__
        compiled: CompiledSchema | None = None
        stages = self._resolve_stage_order()
        last_error: Exception | None = None

        for stage in stages:
            try:
                if stage == "native":
                    result, payload = await self._call_parse(request)
                    self._log_stage(request, stage, logging.INFO, "Mistral parse successful", schema_name=schema_name)
                    return result, list(iter_json_chunks(payload))
                if stage == "json_schema":
                    if compiled is None:
                        compiled = self._compile_schema(request)
                    result, payload = await self._call_json_schema(request, compiled)
                    self._log_stage(request, stage, logging.INFO, "Mistral JSON schema successful", schema_name=schema_name)
                    return result, list(iter_json_chunks(payload))
                if stage == "json_mode":
                    if compiled is None:
                        try:
                            compiled = self._compile_schema(request)
                        except SchemaTooComplexError as schema_err:
                            self._log_stage(
                                request,
                                stage,
                                logging.WARNING,
                                "Schema too complex for structured compilation; falling back to raw json_mode",
                                schema_name=schema_name,
                                error=str(schema_err),
                            )
                            compiled = None
                    result, payload = await self._call_json_mode(request, compiled, schema_name)
                    self._log_stage(request, stage, logging.INFO, "Mistral json_mode successful", schema_name=schema_name)
                    return result, list(iter_json_chunks(payload))
            except SchemaTooComplexError as schema_err:
                self._log_stage(
                    request,
                    stage,
                    logging.WARNING,
                    "Schema compilation failed, retrying with fallback",
                    schema_name=schema_name,
                    error=str(schema_err),
                )
                compiled = None
                last_error = schema_err
                continue
            except StructuredOutputError as err:
                last_error = err
                self._log_stage(
                    request,
                    stage,
                    logging.WARNING,
                    "Structured output stage failed",
                    schema_name=schema_name,
                    error=str(err),
                )
                continue
        raise StructuredOutputError(
            f"Mistral structured output failed after retries: {last_error}" if last_error else "Mistral structured output failed"
        )

    def _resolve_stage_order(self) -> list[str]:
        if self._so_mode == "json_schema":
            return ["json_schema", "json_mode"]
        if self._so_mode == "json_mode":
            return ["json_mode"]
        # default: native first
        return ["native", "json_schema", "json_mode"]

    def _compile_schema(self, request: LLMCompletionRequest) -> CompiledSchema:
        assert request.response_model is not None
        return self._compiler.compile(request.response_model)

    async def _call_parse(self, request: LLMCompletionRequest) -> tuple[LLMCompletionResult, str]:
        assert request.response_model is not None
        kwargs = self._build_request_kwargs(request)
        response: ParsedChatCompletionResponse[BaseModel] = await self._chat.parse_async(
            response_format=request.response_model,
            **kwargs,
        )
        if not response.choices:
            raise StructuredOutputError("Mistral parse returned no choices")
        parsed_model = getattr(response.choices[0].message, "parsed", None)
        if parsed_model is None:
            raise StructuredOutputError("Mistral parse response missing parsed payload")
        json_payload = parsed_model.model_dump_json(indent=2)
        result = LLMCompletionResult(content=json_payload, parsed=parsed_model, raw=response)
        return result, json_payload

    async def _call_json_schema(
        self, request: LLMCompletionRequest, compiled: CompiledSchema
    ) -> tuple[LLMCompletionResult, str]:
        assert request.response_model is not None
        kwargs = self._build_request_kwargs(request)
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": compiled.name,
                "schema": compiled.schema,
                "strict": self._strict,
            },
        }
        response: ChatCompletionResponse = await self._chat.complete_async(response_format=response_format, **kwargs)
        payload = self._extract_text_response(response)
        try:
            parsed_json = json.loads(payload)
        except json.JSONDecodeError as err:
            raise StructuredOutputError("Mistral JSON schema response is not valid JSON") from err
        structured = compiled.transform(parsed_json)
        try:
            model_instance = request.response_model.model_validate(structured)
        except ValidationError as err:
            raise StructuredOutputError("Mistral JSON schema response failed validation") from err
        json_payload = model_instance.model_dump_json(indent=2)
        result = LLMCompletionResult(content=json_payload, parsed=model_instance, raw=response)
        return result, json_payload

    async def _call_json_mode(
        self,
        request: LLMCompletionRequest,
        compiled: CompiledSchema | None,
        schema_name: str,
    ) -> tuple[LLMCompletionResult, str]:
        assert request.response_model is not None
        kwargs = self._build_request_kwargs(request)
        schema_dict = compiled.schema if compiled is not None else request.response_model.model_json_schema()
        schema_text = json.dumps(schema_dict, ensure_ascii=False, indent=2)
        json_instruction = (
            "You MUST respond with a strict JSON object that matches the provided schema. "
            "Return only valid JSON without explanations, markdown, or trailing text.\n"
            f"Schema {schema_name}:\n{schema_text}"
        )
        messages = kwargs["messages"]
        if messages and messages[0].get("role") == "system":
            existing = messages[0].get("content") or ""
            messages[0]["content"] = f"{existing}\n\n{json_instruction}" if existing else json_instruction
        else:
            messages.insert(0, {"role": "system", "content": json_instruction})
        kwargs["messages"] = messages
        response: ChatCompletionResponse = await self._chat.complete_async(**kwargs)
        payload = self._extract_text_response(response)
        try:
            parsed_json = json.loads(payload)
        except json.JSONDecodeError:
            try:
                parsed_json = soft_json_parse(payload)
            except Exception as err:
                raise StructuredOutputError("Mistral json_mode response failed to parse") from err
        if not isinstance(parsed_json, Mapping):
            raise StructuredOutputError("json_mode response must be a JSON object")
        structured = compiled.transform(parsed_json) if compiled is not None else parsed_json
        try:
            model_instance = request.response_model.model_validate(structured)
        except ValidationError as err:
            raise StructuredOutputError("json_mode response failed validation") from err
        json_payload = model_instance.model_dump_json(indent=2)
        result = LLMCompletionResult(content=json_payload, parsed=model_instance, raw=response)
        return result, json_payload

    def _extract_text_response(self, response: ChatCompletionResponse) -> str:
        if not response.choices:
            raise StructuredOutputError("Mistral response missing choices")
        message = response.choices[0].message
        text = coerce_content_to_str(getattr(message, "content", None))
        if not text:
            raise StructuredOutputError("Mistral response content is empty")
        return text
