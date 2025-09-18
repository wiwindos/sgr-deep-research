"""Application settings module using Pydantic and EnvYAML.

Loads configuration from YAML file with environment variables support.
"""

import os
from enum import Enum
from functools import cache
from pathlib import Path

from envyaml import EnvYAML
from pydantic import BaseModel, Field, model_validator


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    MISTRAL = "mistral"


class OpenAIConfig(BaseModel):
    """OpenAI API settings."""

    api_key: str = Field(description="API key")
    base_url: str = Field(default="https://api.openai.com/v1", description="Base URL")
    model: str = Field(default="gpt-4o-mini", description="Model to use")
    max_tokens: int = Field(default=8000, description="Maximum number of tokens")
    temperature: float = Field(default=0.4, ge=0.0, le=1.0, description="Generation temperature")
    proxy: str = Field(default="", description="Proxy URL (e.g., socks5://127.0.0.1:1081 or http://127.0.0.1:8080)")


class MistralConfig(BaseModel):
    """Mistral API settings."""

    api_key: str = Field(description="API key")
    base_url: str = Field(default="https://api.mistral.ai", description="Base URL")
    model: str = Field(default="mistral-large-latest", description="Model to use")
    max_tokens: int = Field(default=8000, description="Maximum number of tokens")
    temperature: float = Field(default=0.4, ge=0.0, le=1.0, description="Generation temperature")
    proxy: str = Field(default="", description="Proxy URL (e.g., socks5://127.0.0.1:1081 or http://127.0.0.1:8080)")


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


class AppConfig(BaseModel):
    """Main application configuration."""

    llm_provider: LLMProvider = Field(default=LLMProvider.OPENAI, description="LLM provider to use")
    openai: OpenAIConfig | None = Field(default=None, description="OpenAI settings")
    mistral: MistralConfig | None = Field(default=None, description="Mistral settings")
    tavily: TavilyConfig = Field(description="Tavily settings")
    search: SearchConfig = Field(default_factory=SearchConfig, description="Search settings")
    scraping: ScrapingConfig = Field(default_factory=ScrapingConfig, description="Scraping settings")
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig, description="Execution settings")
    prompts: PromptsConfig = Field(default_factory=PromptsConfig, description="Prompts settings")

    @model_validator(mode="after")
    def _validate_provider_configuration(self):  # type: ignore[override]
        """Ensure configuration for the selected LLM provider is present."""

        if self.llm_provider == LLMProvider.OPENAI and self.openai is None:
            raise ValueError("OpenAI configuration must be provided when llm_provider is 'openai'")
        if self.llm_provider == LLMProvider.MISTRAL and self.mistral is None:
            raise ValueError("Mistral configuration must be provided when llm_provider is 'mistral'")
        return self


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
