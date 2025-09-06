import os
from functools import cache

from settings import get_config

from core.models import SourceData

config = get_config().app_config


class PromptLoader:
    @classmethod
    @cache
    def _load_prompt_file(cls, filename: str) -> str:
        file_path = os.path.join(config.prompts.prompts_dir, filename)

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Prompt file not found: {file_path}")

        try:
            with open(file_path, encoding="utf-8") as f:
                return f.read().strip()
        except IOError as e:
            raise IOError(f"Error reading prompt file {file_path}: {e}") from e

    @classmethod
    def get_tool_function_prompt(cls) -> str:
        return cls._load_prompt_file(config.prompts.tool_function_prompt_file)

    @classmethod
    def get_system_prompt(cls, user_request: str, sources: list[SourceData]) -> str:
        sources_formatted = "\n".join([str(source) for source in sources])
        template = cls._load_prompt_file(config.prompts.system_prompt_file)
        try:
            return template.format(user_request=user_request, sources_formatted=sources_formatted)
        except KeyError as e:
            raise KeyError(f"Missing placeholder in system prompt template: {e}") from e
