import json
import logging
import os
import yaml
from datetime import datetime
from typing import List, Union, Literal, Optional, Dict, Any
try:
    from typing import Annotated  # Python 3.9+
except ImportError:
    from typing_extensions import Annotated  # Python 3.8
from pydantic import BaseModel, Field
from annotated_types import MinLen, MaxLen
from openai import AsyncOpenAI
from tavily import TavilyClient
from rich.console import Console
from rich.panel import Panel

from scraping import fetch_page_content
from settings import get_config
from core.context import ResearchContext



config = get_config().app_config
logger = logging.getLogger(__name__)

class SGRAgent:

    def __init__(self):
        self._context = ResearchContext()
        self.openai_client = AsyncOpenAI(base_url=config.openai.base_url, api_key=config.openai.api_key)
        self.tavily = TavilyClient(config.tavily.api_key)

    def execute(self, research_request: str ):
        if not research_request:
            raise ValueError("Research request cannot be empty")
        while True:
            execute_research_task()



