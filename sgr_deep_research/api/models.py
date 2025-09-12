"""OpenAI-совместимые модели для API endpoints."""

from enum import Enum
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field

from sgr_deep_research.core.agents.sgr_agent import SGRResearchAgent
from sgr_deep_research.core.agents.sgr_auto_tools_agent import SGRAutoToolCallingResearchAgent
from sgr_deep_research.core.agents.sgr_so_tools_agent import SGRSOToolCallingResearchAgent
from sgr_deep_research.core.agents.sgr_tools_agent import SGRToolCallingResearchAgent
from sgr_deep_research.core.agents.tools_agent import ToolCallingResearchAgent


class AgentModel(str, Enum):
    """Available agent models for chat completion."""

    SGR_AGENT = "sgr-agent"
    SGR_TOOLS_AGENT = "sgr-tools-agent"
    SGR_AUTO_TOOLS_AGENT = "sgr-auto-tools-agent"
    SGR_SO_TOOLS_AGENT = "sgr-so-tools-agent"
    TOOLS_AGENT = "tools-agent"


# Маппинг типов агентов на их классы
AGENT_MODEL_MAPPING = {
    AgentModel.SGR_AGENT: SGRResearchAgent,
    AgentModel.SGR_TOOLS_AGENT: SGRToolCallingResearchAgent,
    AgentModel.SGR_AUTO_TOOLS_AGENT: SGRAutoToolCallingResearchAgent,
    AgentModel.SGR_SO_TOOLS_AGENT: SGRSOToolCallingResearchAgent,
    AgentModel.TOOLS_AGENT: ToolCallingResearchAgent,
}


class ChatMessage(BaseModel):
    """Сообщение в чате."""

    role: Literal["system", "user", "assistant", "tool"] = Field(default="user", description="Роль отправителя")
    content: str = Field(description="Содержимое сообщения")


class ChatCompletionRequest(BaseModel):
    """Запрос на создание chat completion."""

    model: AgentModel | str | None = Field(
        default=AgentModel.SGR_AGENT,
        description="Тип агента или идентификатор существующего агента",
        example="sgr-agent",
    )
    messages: List[ChatMessage] = Field(description="Список сообщений")
    stream: bool = Field(default=True, description="Включить потоковый режим")
    max_tokens: int | None = Field(default=1500, description="Максимальное количество токенов")
    temperature: float | None = Field(default=0, description="Температура генерации")


class ChatCompletionChoice(BaseModel):
    """Выбор в ответе chat completion."""

    index: int = Field(description="Индекс выбора")
    message: ChatMessage = Field(description="Сообщение ответа")
    finish_reason: str | None = Field(description="Причина завершения")


class ChatCompletionResponse(BaseModel):
    """Ответ chat completion (не потоковый)."""

    id: str = Field(description="ID ответа")
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(description="Время создания")
    model: str = Field(description="Использованная модель")
    choices: List[ChatCompletionChoice] = Field(description="Список выборов")
    usage: Dict[str, int] | None = Field(default=None, description="Информация об использовании")


class HealthResponse(BaseModel):
    status: Literal["healthy"] = "healthy"
    service: str = Field(default="SGR Deep Research API", description="Название сервиса")


class AgentStateResponse(BaseModel):
    agent_id: str = Field(description="ID агента")
    task: str = Field(description="Задача агента")
    state: str = Field(description="Текущее состояние агента")
    searches_used: int = Field(description="Количество выполненных поисков")
    clarifications_used: int = Field(description="Количество запрошенных уточнений")
    sources_count: int = Field(description="Количество найденных источников")
    current_state: Dict[str, Any] | None = Field(default=None, description="Текущий шаг агента")


class AgentListItem(BaseModel):
    agent_id: str = Field(description="ID агента")
    task: str = Field(description="Задача агента")
    state: str = Field(description="Текущее состояние агента")


class AgentListResponse(BaseModel):
    agents: List[AgentListItem] = Field(description="Список агентов")
    total: int = Field(description="Общее количество агентов")
