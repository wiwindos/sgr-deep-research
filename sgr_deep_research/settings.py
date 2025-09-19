"""Application settings module using Pydantic and EnvYAML.

Loads configuration from YAML file with environment variables support.
"""

import os
from enum import Enum
from functools import cache
from pathlib import Path

from envyaml import EnvYAML
from pydantic import BaseModel, Field


def _env(name: str, default: str | None = None) -> str | None:
    """Return environment variable value with optional default."""

    value = os.environ.get(name)
    if value is None:
        return default
    return value


def _env_int(name: str, default: int | None = None) -> int | None:
    raw = _env(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


class LLMProvider(str, Enum):
    OPENAI = "openai"
    MISTRAL = "mistral"


class OpenAIConfig(BaseModel):
    """OpenAI API settings."""

    api_key: str = Field(default_factory=lambda: _env("OPENAI_API_KEY", ""), description="API key")
    base_url: str = Field(
        default_factory=lambda: _env("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        description="Base URL",
    )
    model: str = Field(
        default_factory=lambda: _env("OPENAI_MODEL", "gpt-4o-mini"),
        description="Model to use",
    )
    max_tokens: int = Field(default_factory=lambda: _env_int("OPENAI_MAX_TOKENS", 8000) or 8000, description="Maximum number of tokens")
    temperature: float = Field(
        default_factory=lambda: _env_float("OPENAI_TEMPERATURE", 0.4),
        ge=0.0,
        le=1.0,
        description="Generation temperature",
    )
    proxy: str = Field(
        default_factory=lambda: _env("OPENAI_PROXY", ""),
        description="Proxy URL (e.g., socks5://127.0.0.1:1081 or http://127.0.0.1:8080)",
    )


class MistralConfig(BaseModel):
    """Mistral API settings."""

    api_key: str = Field(default_factory=lambda: _env("MISTRAL_API_KEY", ""), description="API key")
    base_url: str = Field(
        default_factory=lambda: _env("MISTRAL_BASE_URL", ""),
        description="Base URL override",
    )
    model: str = Field(
        default_factory=lambda: _env("MISTRAL_MODEL", "mistral-large-latest"),
        description="Model to use",
    )
    max_tokens: int | None = Field(
        default_factory=lambda: _env_int("MISTRAL_MAX_TOKENS"),
        description="Maximum number of tokens",
    )
    temperature: float = Field(
        default_factory=lambda: _env_float("MISTRAL_TEMPERATURE", 0.4),
        ge=0.0,
        le=1.0,
        description="Generation temperature",
    )
    so_mode: str = Field(
        default_factory=lambda: _env("MISTRAL_SO_MODE", "native"),
        description="Structured output mode",
    )
    strict: bool = Field(
        default_factory=lambda: _env_bool("MISTRAL_SO_STRICT", True),
        description="Fail when structured output validation fails",
    )
    allow_additional_properties: bool = Field(
        default_factory=lambda: _env_bool("MISTRAL_ALLOW_ADDITIONAL_PROPERTIES", False),
        description="Allow additional properties in compiled schema",
    )


class TavilyConfig(BaseModel):
    """Tavily Search API settings."""

    api_key: str = Field(description="Tavily API key")
    api_base_url: str = Field(default="https://api.tavily.com", description="Tavily API base URL")


class SearchConfig(BaseModel):
    """Search settings."""

    max_results: int = Field(default=10, ge=1, description="Maximum number of search results")


class ScrapingConfig(BaseModel):
    """Web scraping settings."""

    enabled: bool = Field(default=False, description="Enable full text scraping")
    max_pages: int = Field(default=5, gt=0, description="Maximum pages to scrape")
    content_limit: int = Field(default=1500, gt=0, description="Content character limit per source")


class PromptsConfig(BaseModel):
    """Prompts settings."""

    prompts_dir: str = Field(default="prompts", description="Directory with prompts")
    system_prompt_file: str = Field(default="system_prompt.txt", description="System prompt file")


class ExecutionConfig(BaseModel):
    """Application execution settings."""

    max_steps: int = Field(default=6, gt=0, description="Maximum number of execution steps")
    reports_dir: str = Field(default="reports", description="Directory for saving reports")
    logs_dir: str = Field(default="logs", description="Directory for saving bot logs")


class LLMConfig(BaseModel):
    """Global LLM provider configuration."""

    provider: LLMProvider = Field(
        default_factory=lambda: LLMProvider(_env("LLM_PROVIDER", LLMProvider.OPENAI.value))
    )
    model_alias: str | None = Field(
        default_factory=lambda: _env("LLM_MODEL"),
        description="Optional override for default model",
    )

    def resolved_model(self, openai: OpenAIConfig, mistral: MistralConfig) -> str:
        if self.model_alias:
            return self.model_alias
        if self.provider == LLMProvider.MISTRAL:
            return mistral.model
        return openai.model


class AppConfig(BaseModel):
    """Main application configuration."""

    openai: OpenAIConfig = Field(description="OpenAI settings")
    mistral: MistralConfig = Field(default_factory=MistralConfig, description="Mistral settings")
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM provider settings")
    tavily: TavilyConfig = Field(description="Tavily settings")
    search: SearchConfig = Field(default_factory=SearchConfig, description="Search settings")
    scraping: ScrapingConfig = Field(default_factory=ScrapingConfig, description="Scraping settings")
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig, description="Execution settings")
    prompts: PromptsConfig = Field(default_factory=PromptsConfig, description="Prompts settings")


class ServerConfig(BaseModel):
    """Server configuration."""

    host: str = Field(default="0.0.0.0", description="Host to listen on")
    port: int = Field(default=8010, gt=0, le=65535, description="Port to listen on")


@cache
def get_config() -> AppConfig:
    app_config_env: str = os.environ.get("APP_CONFIG", "config.yaml")

    # If path has no directory part, assume it's in current working directory
    if os.path.basename(app_config_env) == app_config_env:
        app_config_path = Path.cwd() / app_config_env
    else:
        app_config_path = Path(app_config_env)

    return AppConfig.model_validate(dict(EnvYAML(str(app_config_path))))
