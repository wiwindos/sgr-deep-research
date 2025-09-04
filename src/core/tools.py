from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Type, ClassVar, TypeVar, Callable
from typing import TYPE_CHECKING

from tavily import TavilyClient

from core.models import SourceData

if TYPE_CHECKING:
    from core.models import ResearchContext
from pydantic import BaseModel, Field, create_model
from core.reasoning_schemas import (
    Clarification,
    GeneratePlan,
    WebSearch,
    AdaptPlan,
    ReportCompletion, NextStep, CreateReport
)
from settings import get_config

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
config = get_config().app_config
# ToDo: find better place for that
tavily = TavilyClient(config.tavily.api_key)


class ToolCallMixin:
    """Mixin to provide tool handling capabilities
    result should be a string or dumped json"""

    def __call__(self, context: ResearchContext) -> str:
        raise NotImplementedError("Execute method must be implemented by subclass")


class ClarificationTool(ToolCallMixin, Clarification):

    def __call__(self, context: ResearchContext) -> str:
        """Handle clarification requests when facing ambiguous user requests"""

        # Mark clarification as used to prevent cycling
        context.clarification_used = True

        if self.unclear_terms:
            logger.info(f"❓ Unclear terms: {', '.join(self.unclear_terms)}")

        logger.info("\nCLARIFYING QUESTIONS:")
        for i, question in enumerate(self.questions, 1):
            logger.info(f"   {i}. {question}")

        if self.assumptions:
            logger.info("\nPossible interpretations:")
            for assumption in self.assumptions:
                logger.info(f"   • {assumption}")

        logger.info("\n⏸️  Research paused - please answer questions above")

        return "\n".join(self.questions)


class GeneratePlanTool(ToolCallMixin, GeneratePlan):

    def __call__(self, context: ResearchContext) -> str:
        """Generate and store research plan based on clear user request"""
        context.plan = self

        logger.info("📋 Research Plan Created:")
        logger.info(f"🎯 Goal: {self.research_goal}")
        logger.info(f"📝 Steps: {len(self.planned_steps)}")
        for i, step in enumerate(self.planned_steps, 1):
            logger.info(f"   {i}. {step}")

        return self.model_dump_json(indent=2, exclude={"reasoning", })


class AdaptPlanTool(ToolCallMixin, AdaptPlan):

    def __call__(self, context: ResearchContext) -> str:
        """Adapt research plan based on new findings"""
        if context.plan:
            context.plan = self

        logger.info("\n🔄 PLAN ADAPTED")
        logger.info("📝 Changes:")
        for change in self.plan_changes:
            logger.info(f"   • {change}")
        logger.info(f"🎯 New goal {self.new_goal}")

        return self.model_dump_json(indent=2, exclude={"reasoning", })


class CreateReportTool(ToolCallMixin, CreateReport):
    def __call__(self, context: ResearchContext) -> str:
        # Debug: Log CreateReport fields
        logger.info("📝 CREATE REPORT FULL DEBUG:")
        logger.info(f"   🌍 Language Reference: '{self.user_request_language_reference}'")
        logger.info(f"   📊 Title: '{self.title}'")
        logger.info(f"   🔍 Reasoning: '{self.reasoning[:150]}...'")
        logger.info(f"   📈 Confidence: {self.confidence}")
        logger.info(f"   📄 Content Preview: '{self.content[:200]}...'")
        # Save report
        reports_dir = config.execution.reports_dir
        os.makedirs(reports_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c for c in self.title if c.isalnum() or c in (' ', '-', '_'))[:50]
        filename = f"{timestamp}_{safe_title}.md"
        filepath = os.path.join(reports_dir, filename)

        # Format full report with sources
        full_content = f"# {self.title}\n\n"
        full_content += f"*Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
        full_content += self.content + "\n\n"
        full_content += "\n".join(["- " + str(source) for source in context.sources.values()])

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_content)

        report = {
            "title": self.title,
            "content": self.content,
            "confidence": self.confidence,
            "sources_count": len(context.sources),
            "word_count": len(self.content.split()),
            "filepath": filepath,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"📄 Report Created: {self.title}")
        logger.info(f"📊 Words: {report['word_count']}, Sources: {report['sources_count']}")
        logger.info(f"💾 Saved: {filepath}")
        logger.info(f"📈 Confidence: {self.confidence}")

        return json.dumps(report, indent=2, ensure_ascii=False)


class ReportCompletionTool(ToolCallMixin, ReportCompletion):

    def __call__(self, context: ResearchContext) -> str:
        """Complete research task"""

        logger.info("\n✅ RESEARCH COMPLETED")
        logger.info(f"📋 Status: {self.status}")

        if self.completed_steps:
            logger.info("📝 Completed steps:")
            for step in self.completed_steps:
                logger.info(f"   • {step}")

        return json.dumps({
            "tool": "report_completion",
            "status": self.status,
            "completed_steps": self.completed_steps
        }, indent=2, ensure_ascii=False)


# ToDo: Looks like some service logic here, need to be divided
class WebSearchTool(ToolCallMixin, WebSearch):

    def __call__(self, context: ResearchContext) -> str:
        """Execute web search with optional content scraping"""

        logger.info(f"🔍 Search query: '{self.query}'")

        # Check if scraping should be enabled
        should_scrape = config.scraping.enabled and self.scrape_content
        if should_scrape:
            logger.info("📄 Scraping enabled - will fetch full content")

        response = tavily.search(
            query=self.query,
            max_results=self.max_results,
            include_answer=True,
            include_raw_content=True
        )
        # Add citations and optionally scrape content
        citations = []

        for i, result in enumerate(response.get('results', []), len(context.sources) + 1):
            url = result.get('url', '')
            title = result.get('title', '')
            if url:
                src = SourceData(number=i, title=title, url=url, snippet=result.get('content', ''))
                # Scrape full content if enabled and within limits
                if should_scrape and i < config.scraping.max_pages:
                    logger.info(f"   📄 Scraping [{i}] {url[:50]}...")
                    src.full_content = result.get('raw_content', '')
                    src.char_count = len(src.full_content) or 0
                citations.append(src)
                context.sources[url] = src

        search_result = {
            "query": self.query,
            "answer": response.get('answer', ''),
            "citations": citations,
            "scraping_enabled": should_scrape,
            "timestamp": datetime.now().isoformat()
        }

        context.searches.append(search_result)

        logger.info(f"🔍 Found {len(citations)} citations")
        for citation in citations:
            logger.info(f"   {str(citation)}")

        formatted_result = f"Search Query: {search_result.get('query', '')}\n\n"

        # Include answer only if it exists (with include_answer=True)
        if search_result.get('answer'):
            formatted_result += f"AI Answer: {search_result.get('answer')}\n\n"

        formatted_result += "Search Results:\n\n"

        for res in citations[:5]:
            if res.full_content:
                content = res.full_content[:config.scraping.content_limit]
                formatted_result += f"{str(res)}\n\n**Full Content (Markdown):**\n{content}\n\n"
            else:
                formatted_result += f"{str(res)}\n{res.snippet}\n\n"
        context.searches_used += 1
        logger.info(formatted_result)
        return formatted_result


TOOL_FUNCTION_PROMPT = """
DECISION PRIORITY (BIAS TOWARD CLARIFICATION):

1. If ANY uncertainty about user request → Clarification
2. If no plan exists and request is clear → GeneratePlan
3. If need to adapt research approach → AdaptPlan
4. If need more information AND searches_done < 3 → WebSearch
5. If searches_done >= 2 OR enough_data = True → CreateReport
6. If report created → ReportCompletion

CLARIFICATION TRIGGERS:
- Unknown terms, acronyms, abbreviations
- Ambiguous requests with multiple interpretations
- Missing context for specialized domains
- Any request requiring assumptions

ANTI-CYCLING RULES:
- Max 1 clarification per session
- Max 3-4 searches per session
- Create report after 2-3 searches regardless of completeness
"""


class NextStepToolStub(NextStep, ToolCallMixin):
    """Stub class for correct autocomplete"""
    pass


class NextStepToolsBuilder:

    tools: ClassVar[list[Type[ToolCallMixin]]] = [
        ClarificationTool,
        GeneratePlanTool,
        WebSearchTool,
        AdaptPlanTool,
        CreateReportTool,
        ReportCompletionTool,
    ]

    @classmethod
    def _create_tool_types_union(cls, exclude: list[Type[ToolCallMixin]] | None = None):
        if exclude is None:
            exclude = []
        enabled_tools_types = [tool for tool in cls.tools if tool not in exclude]
        if len(enabled_tools_types) == 1:
            return enabled_tools_types[0]

        from functools import reduce
        import operator
        return reduce(operator.or_, enabled_tools_types)

    @classmethod
    def build_NextStepTools(cls, exclude: list[Type[ToolCallMixin]] | None = None) -> Type[NextStepToolStub]:
        return create_model(
            "NextStepTools",
            __base__=NextStepToolStub,
            function=(cls._create_tool_types_union(exclude), Field(description=TOOL_FUNCTION_PROMPT))
        )