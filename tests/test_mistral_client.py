import asyncio
from types import SimpleNamespace

import pytest

from sgr_deep_research.core.llm.base import (
    LLMCompletionRequest,
    LLMCompletionResult,
    StructuredOutputError,
)
from sgr_deep_research.core.llm.mistral_client import MistralLLMClient, MistralStructuredStream
from sgr_deep_research.core.tools import ReasoningTool
from sgr_deep_research.settings import (
    AppConfig,
    ExecutionConfig,
    LLMConfig,
    LLMProvider,
    MistralConfig,
    OpenAIConfig,
    PromptsConfig,
    ScrapingConfig,
    SearchConfig,
    TavilyConfig,
)


@pytest.fixture()
def app_config() -> AppConfig:
    return AppConfig(
        openai=OpenAIConfig(
            api_key="test",
            base_url="http://localhost",
            model="gpt-test",
            max_tokens=128,
            temperature=0.1,
            proxy="",
        ),
        mistral=MistralConfig(
            api_key="mistral-test",
            base_url="",
            model="mistral-large-latest",
            max_tokens=128,
            temperature=0.1,
            so_mode="native",
            strict=True,
            allow_additional_properties=False,
        ),
        llm=LLMConfig(provider=LLMProvider.MISTRAL),
        tavily=TavilyConfig(api_key="tavily-key"),
        search=SearchConfig(),
        scraping=ScrapingConfig(),
        execution=ExecutionConfig(),
        prompts=PromptsConfig(),
    )


def test_mistral_fallback_json_mode(app_config):
    async def run():
        client = MistralLLMClient(app_config)

        reasoning = ReasoningTool(
            reasoning_steps=["step-1", "step-2"],
            current_situation="Situation",
            plan_status="Status",
            enough_data=True,
            remaining_steps=["next"],
            task_completed=False,
        )
        json_payload = reasoning.model_dump_json(indent=2)
        stub_response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json_payload))])

        async def parse_async(**kwargs):
            raise StructuredOutputError("parse failed")

        async def complete_async(**kwargs):
            if "response_format" in kwargs and kwargs["response_format"] is not None:
                raise StructuredOutputError("schema failed")
            return stub_response

        client._chat = SimpleNamespace(parse_async=parse_async, complete_async=complete_async)

        request = LLMCompletionRequest(
            messages=[{"role": "user", "content": "hello"}],
            response_model=ReasoningTool,
            model=app_config.mistral.model,
        )
        result, chunks = await client._complete_structured(request)

        assert result.parsed is not None
        assert result.parsed.model_dump() == reasoning.model_dump()
        assert "".join(chunks) == json_payload

    asyncio.run(run())


def test_structured_stream_emits_chunks():
    async def run():
        expected = LLMCompletionResult(content="{}", parsed=None)

        async def complete():
            return expected, ["chunk-1", "chunk-2"]

        stream = MistralStructuredStream(complete)
        collected = []
        async with stream as active_stream:
            async for delta in active_stream:
                collected.append(delta.content)
            final = await active_stream.get_final_response()
        assert collected == ["chunk-1", "chunk-2"]
        assert final is expected

    asyncio.run(run())
