from __future__ import annotations

from sgr_deep_research.core.llm.base import LLMClient
from sgr_deep_research.core.llm.mistral_client import MistralLLMClient
from sgr_deep_research.core.llm.openai_client import OpenAILLMClient
from sgr_deep_research.settings import AppConfig, LLMProvider


def create_llm_client(config: AppConfig) -> LLMClient:
    """Create LLM client instance based on configuration."""

    if config.llm.provider == LLMProvider.MISTRAL:
        return MistralLLMClient(config)
    return OpenAILLMClient(config)
