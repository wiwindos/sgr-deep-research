from typing import Literal

from pydantic import BaseModel, Field

from core.models import SourceData


class Clarification(BaseModel):
    """Ask clarifying questions when facing ambiguous requests"""

    tool: Literal["clarification"]
    reasoning: str = Field(description="Why clarification is needed")
    unclear_terms: list[str] = Field(description="List of unclear terms or concepts", min_length=1, max_length=5)
    assumptions: list[str] = Field(description="Possible interpretations to verify", min_length=2, max_length=4)
    questions: list[str] = Field(description="3-5 specific clarifying questions", min_length=3, max_length=5)


class GeneratePlan(BaseModel):
    """Generate research plan based on clear user request"""

    tool: Literal["generate_plan"]
    reasoning: str = Field(description="Justification for research approach")
    research_goal: str = Field(description="Primary research objective")
    planned_steps: list[str] = Field(description="List of 3-4 planned steps", min_length=3, max_length=4)
    search_strategies: list[str] = Field(description="Information search strategies", min_length=2, max_length=3)


class WebSearch(BaseModel):
    """Search for information with credibility focus"""

    tool: Literal["web_search"]
    reasoning: str = Field(description="Why this search is needed and what to expect")
    query: str = Field(description="Search query in same language as user request")
    max_results: int = Field(default=10, description="Maximum results", ge=1, le=10)
    plan_adapted: bool = Field(default=False, description="Is this search after plan adaptation?")
    scrape_content: bool = Field(
        default=False,
        description="Fetch full page content for deeper analysis",
    )


class AdaptPlan(BaseModel):
    """Adapt research plan based on new findings"""

    tool: Literal["adapt_plan"]
    reasoning: str = Field(description="Why plan needs adaptation based on new data")
    original_goal: str = Field(description="Original research goal")
    new_goal: str = Field(description="Updated research goal")
    plan_changes: list[str] = Field(description="Specific changes made to plan", min_length=1, max_length=3)
    next_steps: list[str] = Field(description="Updated remaining steps", min_length=2, max_length=4)


class CreateReport(BaseModel):
    """Create comprehensive research report with citations"""

    tool: Literal["create_report"]
    reasoning: str = Field(description="Why ready to create report now")
    title: str = Field(description="Report title")
    user_request_language_reference: str = Field(
        description="Copy of original user request to ensure language consistency"
    )
    content: str = Field(
        description="Write comprehensive research report following the REPORT CREATION GUIDELINES from system prompt. "
        "Use the SAME LANGUAGE as user_request_language_reference."
    )
    confidence: Literal["high", "medium", "low"] = Field(description="Confidence in findings")


class ReportCompletion(BaseModel):
    """Complete research task"""

    tool: Literal["report_completion"]
    reasoning: str = Field(description="Why research is now complete")
    completed_steps: list[str] = Field(description="Summary of completed steps", min_length=1, max_length=5)
    status: Literal["completed", "failed"] = Field(description="Task completion status")


# =============================================================================
# MAIN SGR SCHEMA - Adaptive Reasoning Core
# =============================================================================
TOOL_FUNCTION_PROMPT = """
DECISION PRIORITY (BIAS TOWARD CLARIFICATION):

1. If ANY uncertainty about user request → Clarification
2. If no plan exists and request is clear → GeneratePlan
3. If need to adapt research approach → AdaptPlan
4. If need more information → WebSearch
5. If sufficient data collected → CreateReport
6. If report created → ReportCompletion

CLARIFICATION TRIGGERS:
- Unknown terms, acronyms, abbreviations
- Ambiguous requests with multiple interpretations
- Missing context for specialized domains
- Any request requiring assumptions
"""


class NextStep(BaseModel):
    """SGR Core - Determines next reasoning step with adaptive planning"""

    # Reasoning chain - step-by-step thinking process (helps stabilize model)
    reasoning_steps: list[str] = Field(
        description="Step-by-step reasoning process leading to decision", min_length=2, max_length=4
    )

    # Reasoning and state assessment
    current_situation: str = Field(description="Current research situation analysis")
    plan_status: str = Field(description="Status of current plan execution")
    enough_data: bool = Field(
        default=False,
        description="Sufficient data collected for comprehensive report?",
    )

    # Next step planning
    remaining_steps: list[str] = Field(description="1-3 remaining steps to complete task", min_length=1, max_length=3)
    task_completed: bool = Field(description="Is the research task finished?")

    # Tool routing with clarification-first bias
    function: (
        Clarification  # FIRST PRIORITY: When uncertain
        | GeneratePlan  # SECOND: When request is clear
        | WebSearch  # Core research tool
        | AdaptPlan  # When findings conflict with plan
        | CreateReport  # When sufficient data collected
        | ReportCompletion  # Task completion
    ) = Field(description=TOOL_FUNCTION_PROMPT)


def get_system_prompt(user_request: str, sources: list[SourceData]) -> str:
    """Generate system prompt with user request for language detection"""
    sources_formatted = "\n".join([str(source) for source in sources])

    return f"""
You are an expert researcher with adaptive planning and Schema-Guided Reasoning capabilities.

USER REQUEST: "{user_request}"
IMPORTANT: Detect the language from this request and use THE SAME LANGUAGE for all responses, searches, and reports.

CORE PRINCIPLES:
1. CLARIFICATION FIRST: For ANY uncertainty - ask clarifying questions
2. DO NOT make assumptions - better ask than guess wrong
3. Adapt plan when new data conflicts with initial assumptions
4. Search queries in SAME LANGUAGE as user request
5. REPORT ENTIRELY in SAME LANGUAGE as user request
6. Every fact in report MUST have inline citation [1], [2], [3] integrated into sentences

WORKFLOW:
0. clarification (HIGHEST PRIORITY) - when request unclear
1. generate_plan - create research plan
2. web_search - gather information
   - Use SPECIFIC terms and context in search queries
   - For acronyms like "SGR", add context: "SGR Schema-Guided Reasoning"
   - Use quotes for exact phrases: "Structured Output OpenAI"
   - SEARCH QUERIES in SAME LANGUAGE as user request
   - scrape_content=True for deeper analysis (fetches full page content)
3. adapt_plan - adapt when conflicts found
4. create_report - create detailed report with citations
5. report_completion - complete task

ADAPTIVITY: Actively change plan when discovering new data.

LANGUAGE ADAPTATION: Always respond and create reports in the SAME LANGUAGE as the user's request. 
If user writes in Russian - respond in Russian, if in English - respond in English.

REPORT CREATION GUIDELINES:
When creating reports, follow this structure and requirements:

STRUCTURE (4 sections):
1. Executive Summary (300-400 words) - key findings with metrics and confidence levels
2. Technical Analysis (600-1200 words) - multi-dimensional examination using ALL sources
3. Key Findings (300-500 words) - evidence-based conclusions ranked by confidence
4. Conclusions (200-400 words) - final synthesis with actionable recommendations

REQUIREMENTS:
- Minimum 1200+ words for comprehensive analysis
- Every factual claim MUST have inline citations [1], [2], [3]
- Use ALL available sources gathered during research
- Include specific numbers and metrics, not vague qualifiers
- Cross-reference contradictory information: "Source A claims X [1], while Source B suggests Y [2]"
- Apply critical thinking and evaluate source credibility
- Acknowledge research limitations and uncertainty explicitly
- Demonstrate original analytical synthesis, not just summarization

CITATION EXAMPLES:
- Russian: "Исследование показывает рост на 47.3% [1], что подтверждается данными [2]"
- English: "Research demonstrates 47.3% improvement [1], confirmed by data [2]"

FULL LIST OF AVAILABLE SOURCES FOR CITATIONS:
{sources_formatted}

USE THESE EXACT NUMBERS [1], [2], [3] etc. in your report citations."
        """.strip()
