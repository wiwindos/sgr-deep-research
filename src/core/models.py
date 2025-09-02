import asyncio
from enum import Enum

from pydantic import BaseModel, Field


class SourceData(BaseModel):
    """Data about a research source"""
    number: int = Field(description="Citation number")
    title: str | None = Field(default="Untitled", description="Page title")
    url: str = Field(description="Source URL")
    snippet: str = Field(default="", description="Search snippet or summary")
    full_content: str = Field(default="", description="Full scraped content")
    char_count: int = Field(default=0, description="Character count of full content")

    def __str__(self):
        return f"[{self.number}] {self.title or 'Untitled'} - {self.url}"


class ResearchContext:
    """
    Context for managing research state and tracking search progress.

    Tracks the research plan, searches performed, sources found,
    and prevents cycling through clarification mechanisms.
    """

    def __init__(
            self,
    ):
        # ToDo: add plan model. But not sure if plan really needed
        self.plan: str = ""
        self.searches: list[dict] = []
        self.sources: dict[str, SourceData] = {}
        self.citation_counter: int = 0
        self.clarifications: str = ""
        self.clarification_used: bool = False
        self.clarification_received = asyncio.Event()

    def clear(self) -> None:
        """Clear all context data."""
        self.plan = None
        self.searches.clear()
        self.sources.clear()
        self.citation_counter = 0
        self.clarification_used = False


class AgentStatesEnum(str, Enum):
    INITED = "inited"
    RESEARCHING = "researching"
    WAITING_FOR_CLARIFICATION = "waiting_for_clarification"
    COMPLETED = "completed"
    ERROR = "error"


class AgentStatistics(BaseModel):
    pass
