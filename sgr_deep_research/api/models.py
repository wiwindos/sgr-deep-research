"""OpenAI-совместимые модели для API endpoints."""

from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Сообщение в чате."""

    role: Literal["system", "user", "assistant", "tool"] = Field(default="user", description="Роль отправителя")
    content: str = Field(description="Содержимое сообщения")


class ChatCompletionRequest(BaseModel):
    """Запрос на создание chat completion."""

    model: str | None = Field(
        default=None, description="Идентификатор агента", example="sgr_agent_35702b10-4d4e-426f-9b33-b170032e37df"
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
