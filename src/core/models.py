import asyncio
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from core.reasoning_schemas import NextStep


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


class SearchResult(BaseModel):
    """Search result with query, answer, and sources"""

    query: str = Field(description="Search query")
    answer: str = Field(default="", description="AI-generated answer from search")
    citations: list[SourceData] = Field(default_factory=list, description="List of source citations")
    timestamp: datetime = Field(default_factory=datetime.now, description="Search execution timestamp")

    def __str__(self):
        return f"Search: '{self.query}' ({len(self.citations)} sources)"


class ResearchContext:
    """
    Context for managing research state and tracking search progress.

    Tracks the research plan, searches performed, sources found,
    and prevents cycling through clarification mechanisms.
    """

    def __init__(self):
        self.current_state: NextStep | None = None

        self.searches: list[SearchResult] = []
        self.sources: dict[str, SourceData] = {}

        self.searches_used: int = 0

        self.clarifications_used: int = 0
        self.clarification_received = asyncio.Event()


class AgentStatesEnum(str, Enum):
    INITED = "inited"
    RESEARCHING = "researching"
    WAITING_FOR_CLARIFICATION = "waiting_for_clarification"
    COMPLETED = "completed"
    ERROR = "error"


class AgentStatistics(BaseModel):
    pass
