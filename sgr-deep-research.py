#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SGR Research Agent - Schema-Guided Reasoning with Adaptive Planning
Clean implementation following SGR principles with clarification-first approach
"""

import json
import os
import yaml
from datetime import datetime
from typing import List, Union, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field
from openai import OpenAI
from tavily import TavilyClient
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

# =============================================================================
# CONFIGURATION
# =============================================================================

def load_config():
    """Load configuration from config.yaml and environment variables"""
    config = {
        'openai_api_key': os.getenv('OPENAI_API_KEY', ''),
        'openai_base_url': os.getenv('OPENAI_BASE_URL', ''),
        'openai_model': os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
        'max_tokens': int(os.getenv('MAX_TOKENS', '8000')),
        'temperature': float(os.getenv('TEMPERATURE', '0.4')),
        'tavily_api_key': os.getenv('TAVILY_API_KEY', ''),
        'max_search_results': int(os.getenv('MAX_SEARCH_RESULTS', '10')),
        'max_execution_steps': int(os.getenv('MAX_EXECUTION_STEPS', '6')),
        'reports_directory': os.getenv('REPORTS_DIRECTORY', 'reports'),
        'russian_threshold': float(os.getenv('RUSSIAN_THRESHOLD', '0.3')),
    }
    
    if os.path.exists('config.yaml'):
        try:
            with open('config.yaml', 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
            
            if yaml_config:
                if 'openai' in yaml_config:
                    openai_cfg = yaml_config['openai']
                    config['openai_api_key'] = openai_cfg.get('api_key', config['openai_api_key'])
                    config['openai_base_url'] = openai_cfg.get('base_url', config['openai_base_url'])
                    config['openai_model'] = openai_cfg.get('model', config['openai_model'])
                    config['max_tokens'] = openai_cfg.get('max_tokens', config['max_tokens'])
                    config['temperature'] = openai_cfg.get('temperature', config['temperature'])
                
                if 'tavily' in yaml_config:
                    config['tavily_api_key'] = yaml_config['tavily'].get('api_key', config['tavily_api_key'])
                
                if 'search' in yaml_config:
                    config['max_search_results'] = yaml_config['search'].get('max_results', config['max_search_results'])
                
                if 'execution' in yaml_config:
                    config['max_execution_steps'] = yaml_config['execution'].get('max_steps', config['max_execution_steps'])
                    config['reports_directory'] = yaml_config['execution'].get('reports_dir', config['reports_directory'])
                
        except Exception as e:
            print(f"Warning: Could not load config.yaml: {e}")
    
    return config

CONFIG = load_config()

# Check required parameters
if not CONFIG['openai_api_key']:
    print("ERROR: OPENAI_API_KEY not set in config.yaml or environment")
    exit(1)

if not CONFIG['tavily_api_key']:
    print("ERROR: TAVILY_API_KEY not set in config.yaml or environment")
    exit(1)

# =============================================================================
# SGR SCHEMAS - Core Schema-Guided Reasoning Definitions
# =============================================================================

class Clarification(BaseModel):
    """Ask clarifying questions when facing ambiguous requests"""
    tool: Literal["clarification"]
    reasoning: str = Field(description="Why clarification is needed")
    unclear_terms: List[str] = Field(description="List of unclear terms or concepts")
    questions: List[str] = Field(description="3-5 specific clarifying questions")
    assumptions: List[str] = Field(description="Possible interpretations to verify")

class GeneratePlan(BaseModel):
    """Generate research plan based on clear user request"""
    tool: Literal["generate_plan"]
    reasoning: str = Field(description="Justification for research approach")
    research_goal: str = Field(description="Primary research objective")
    planned_steps: List[str] = Field(description="List of 3-4 planned steps")
    search_strategies: List[str] = Field(description="Information search strategies")

class WebSearch(BaseModel):
    """Search for information with credibility focus"""
    tool: Literal["web_search"] 
    reasoning: str = Field(description="Why this search is needed and what to expect")
    query: str = Field(description="Search query in same language as user request")
    max_results: int = Field(default=10, description="Maximum results (1-15)")
    plan_adapted: bool = Field(default=False, description="Is this search after plan adaptation?")

class AdaptPlan(BaseModel):
    """Adapt research plan based on new findings"""
    tool: Literal["adapt_plan"]
    reasoning: str = Field(description="Why plan needs adaptation based on new data")
    original_goal: str = Field(description="Original research goal")
    new_goal: str = Field(description="Updated research goal")
    plan_changes: List[str] = Field(description="Specific changes made to plan")
    next_steps: List[str] = Field(description="Updated remaining steps")

class CreateReport(BaseModel):
    """Create comprehensive research report with citations"""
    tool: Literal["create_report"]
    reasoning: str = Field(description="Why ready to create report now")
    title: str = Field(description="Report title")
    content: str = Field(description="""
    DETAILED technical content (800+ words) with citations [1], [2], [3].
    
    CRITICAL REQUIREMENTS:
    - Include in-text citations for EVERY fact!
    - Write ENTIRELY in the SAME LANGUAGE as user request
    - Example: "Apple M5 uses 3nm process [1]"
    
    Structure:
    1. Executive Summary 
    2. Technical Analysis (with citations)
    3. Key Findings
    4. Conclusions
    
    LANGUAGE: Must match user's request language (Russian/English/etc).
    """)
    confidence: Literal["high", "medium", "low"] = Field(description="Confidence in findings")

class ReportCompletion(BaseModel):
    """Complete research task"""
    tool: Literal["report_completion"]
    reasoning: str = Field(description="Why research is now complete")
    completed_steps: List[str] = Field(description="Summary of completed steps")
    status: Literal["completed", "failed"] = Field(description="Task completion status")

# =============================================================================
# MAIN SGR SCHEMA - Adaptive Reasoning Core
# =============================================================================

class NextStep(BaseModel):
    """SGR Core - Determines next reasoning step with adaptive planning"""
    
    # Reasoning and state assessment
    current_situation: str = Field(description="Current research situation analysis")
    plan_status: str = Field(description="Status of current plan execution")
    
    # Adaptive planning logic
    new_data_conflicts_plan: bool = Field(
        default=False,
        description="Do recent findings conflict with current plan?"
    )
    
    # Progress tracking  
    searches_done: int = Field(default=0, description="Number of searches completed")
    enough_data: bool = Field(default=False, description="Sufficient data for report?")
    
    # Next step planning
    remaining_steps: List[str] = Field(description="1-3 remaining steps to complete task")
    task_completed: bool = Field(description="Is the research task finished?")
    
    # Tool routing with clarification-first bias
    function: Union[
        Clarification,      # FIRST PRIORITY: When uncertain
        GeneratePlan,       # SECOND: When request is clear 
        WebSearch,          # Core research tool
        AdaptPlan,          # When findings conflict with plan
        CreateReport,       # When sufficient data collected
        ReportCompletion    # Task completion
    ] = Field(description="""
    DECISION PRIORITY (BIAS TOWARD CLARIFICATION):
    
    1. If ANY uncertainty about user request → Clarification
    2. If no plan exists and request is clear → GeneratePlan  
    3. If new findings conflict with plan → AdaptPlan
    4. If need more information → WebSearch
    5. If sufficient data (2+ searches) → CreateReport
    6. If report created → ReportCompletion
    
    CLARIFICATION TRIGGERS:
    - Unknown terms, acronyms, abbreviations
    - Ambiguous requests with multiple interpretations
    - Missing context for specialized domains
    - Any request requiring assumptions
    
    ANTI-CYCLING: Max 1 clarification per session
    """)

# =============================================================================
# PROMPTS - System Instructions
# =============================================================================

def get_system_prompt(language: str = "en") -> str:
    """Generate system prompt based on detected language"""
    
    if language == "ru":
        return """
Вы эксперт-исследователь с возможностями адаптивного планирования и Schema-Guided Reasoning.

ОСНОВНЫЕ ПРИНЦИПЫ:
1. ПРИОРИТЕТ УТОЧНЕНИЙ: При ЛЮБОЙ неясности - запрашивайте уточнения
2. НЕ делайте предположений - лучше спросить, чем угадать неправильно
3. Адаптируйте план, когда новые данные противоречат первоначальным предположениям
4. Поисковые запросы НА ТОМ ЖЕ ЯЗЫКЕ, что и запрос пользователя
5. ОТЧЕТ ПОЛНОСТЬЮ НА ТОМ ЖЕ ЯЗЫКЕ, что и запрос пользователя
6. Каждый факт в отчете ОБЯЗАТЕЛЬНО должен иметь цитату [1], [2], [3]

РАБОЧИЙ ПРОЦЕСС:
0. clarification (ВЫСШИЙ ПРИОРИТЕТ) - при неясности запроса
1. generate_plan - создать план исследования  
2. web_search - найти информацию (2-3 поиска)
3. adapt_plan - адаптировать при противоречиях
4. create_report - создать детальный отчет с цитатами
5. report_completion - завершить задачу

АНТИ-ЦИКЛИЧНОСТЬ: Максимум 1 запрос уточнения на сессию.

АДАПТИВНОСТЬ: Активно изменяйте план при обнаружении новых данных.
        """.strip()
    else:
        return """
You are an expert researcher with adaptive planning and Schema-Guided Reasoning capabilities.

CORE PRINCIPLES:
1. CLARIFICATION FIRST: For ANY uncertainty - ask clarifying questions
2. DO NOT make assumptions - better ask than guess wrong
3. Adapt plan when new data conflicts with initial assumptions  
4. Search queries in SAME LANGUAGE as user request
5. REPORT ENTIRELY in SAME LANGUAGE as user request
6. Every fact in report MUST have citation [1], [2], [3]

WORKFLOW:
0. clarification (HIGHEST PRIORITY) - when request unclear
1. generate_plan - create research plan
2. web_search - gather information (2-3 searches)
3. adapt_plan - adapt when conflicts found
4. create_report - create detailed report with citations
5. report_completion - complete task

ANTI-CYCLING: Maximum 1 clarification request per session.

ADAPTIVITY: Actively change plan when discovering new data.
        """.strip()

# =============================================================================
# INITIALIZATION
# =============================================================================

# Initialize OpenAI client with base_url if provided
openai_kwargs = {'api_key': CONFIG['openai_api_key']}
if CONFIG['openai_base_url']:
    openai_kwargs['base_url'] = CONFIG['openai_base_url']

client = OpenAI(**openai_kwargs)
tavily = TavilyClient(CONFIG['tavily_api_key'])
console = Console()
print = console.print

# Simple in-memory context
CONTEXT = {
    "plan": None,
    "searches": [],
    "sources": {},  # url -> citation_number mapping
    "citation_counter": 0,
    "clarification_used": False  # Anti-cycling mechanism
}

# =============================================================================
# UTILITIES
# =============================================================================

def detect_language(text: str) -> str:
    """Simple language detection"""
    russian_chars = sum(1 for char in text if 'а' <= char.lower() <= 'я' or char in 'ё')
    total_chars = sum(1 for char in text if char.isalpha())
    
    if total_chars == 0:
        return "en"
    
    russian_ratio = russian_chars / total_chars
    return "ru" if russian_ratio > CONFIG['russian_threshold'] else "en"

def add_citation(url: str, title: str = "") -> int:
    """Add source and return citation number"""
    if url in CONTEXT["sources"]:
        return CONTEXT["sources"][url]["number"]
    
    CONTEXT["citation_counter"] += 1
    number = CONTEXT["citation_counter"]
    
    CONTEXT["sources"][url] = {
        "number": number,
        "title": title,
        "url": url
    }
    
    return number

def format_sources() -> str:
    """Format sources for report"""
    if not CONTEXT["sources"]:
        return ""
    
    sources_text = "\n## Источники\n" if detect_language(str(CONTEXT)) == "ru" else "\n## Sources\n"
    
    for url, data in CONTEXT["sources"].items():
        number = data["number"]
        title = data["title"]
        if title:
            sources_text += f"[{number}] {title} - {url}\n"
        else:
            sources_text += f"[{number}] {url}\n"
    
    return sources_text

# =============================================================================
# DISPATCH - Tool Execution
# =============================================================================

def dispatch(cmd: BaseModel, context: Dict[str, Any]) -> Any:
    """Execute SGR commands"""
    
    if isinstance(cmd, Clarification):
        # Mark clarification as used to prevent cycling
        context["clarification_used"] = True
        
        print(f"\n🤔 [bold yellow]CLARIFICATION NEEDED[/bold yellow]")
        print(f"💭 Reason: {cmd.reasoning}\n")
        
        if cmd.unclear_terms:
            print(f"❓ [bold]Unclear terms:[/bold] {', '.join(cmd.unclear_terms)}")
        
        print(f"\n[bold cyan]CLARIFYING QUESTIONS:[/bold cyan]")
        for i, question in enumerate(cmd.questions, 1):
            print(f"   {i}. {question}")
        
        if cmd.assumptions:
            print(f"\n[bold green]Possible interpretations:[/bold green]")
            for assumption in cmd.assumptions:
                print(f"   • {assumption}")
        
        print(f"\n[bold yellow]⏸️  Research paused - please answer questions above[/bold yellow]")
        
        return {
            "tool": "clarification",
            "questions": cmd.questions,
            "status": "waiting_for_user"
        }
    
    elif isinstance(cmd, GeneratePlan):
        plan = {
            "research_goal": cmd.research_goal,
            "planned_steps": cmd.planned_steps,
            "search_strategies": cmd.search_strategies,
            "created_at": datetime.now().isoformat()
        }
        
        context["plan"] = plan
        
        print(f"📋 [bold]Research Plan Created:[/bold]")
        print(f"🎯 Goal: {cmd.research_goal}")
        print(f"📝 Steps: {len(cmd.planned_steps)}")
        for i, step in enumerate(cmd.planned_steps, 1):
            print(f"   {i}. {step}")
        
        return plan
    
    elif isinstance(cmd, WebSearch):
        print(f"🔍 [bold cyan]Search query:[/bold cyan] [white]'{cmd.query}'[/white]")
        
        try:
            response = tavily.search(
                query=cmd.query,
                max_results=cmd.max_results,
                include_answer=True
            )
            
            # Add citations
            citation_numbers = []
            for result in response.get('results', []):
                url = result.get('url', '')
                title = result.get('title', '')
                if url:
                    citation_num = add_citation(url, title)
                    citation_numbers.append(citation_num)
            
            search_result = {
                "query": cmd.query,
                "answer": response.get('answer', ''),
                "results": response.get('results', []),
                "citation_numbers": citation_numbers,
                "timestamp": datetime.now().isoformat()
            }
            
            context["searches"].append(search_result)
            
            print(f"🔍 Found {len(citation_numbers)} sources")
            for i, (result, citation_num) in enumerate(zip(response.get('results', [])[:5], citation_numbers), 1):
                print(f"   {i}. [{citation_num}] {result.get('url', '')}")
            
            return search_result
            
        except Exception as e:
            error_msg = f"Search error: {str(e)}"
            print(f"❌ {error_msg}")
            return {"error": error_msg}
    
    elif isinstance(cmd, AdaptPlan):
        if context.get("plan"):
            context["plan"]["research_goal"] = cmd.new_goal
            context["plan"]["planned_steps"] = cmd.next_steps
            context["plan"]["adapted"] = True
            context["plan"]["adaptations"] = context["plan"].get("adaptations", []) + [cmd.plan_changes]
        
        print(f"\n🔄 [bold yellow]PLAN ADAPTED![/bold yellow]")
        print(f"📝 [bold]Changes:[/bold]")
        for change in cmd.plan_changes:
            print(f"   • [yellow]{change}[/yellow]")
        print(f"🎯 [bold green]New goal:[/bold green] {cmd.new_goal}")
        
        return {
            "tool": "adapt_plan",
            "original_goal": cmd.original_goal,
            "new_goal": cmd.new_goal,
            "changes": cmd.plan_changes
        }
    
    elif isinstance(cmd, CreateReport):
        # Save report
        os.makedirs(CONFIG['reports_directory'], exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c for c in cmd.title if c.isalnum() or c in (' ', '-', '_'))[:50]
        filename = f"{timestamp}_{safe_title}.md"
        filepath = os.path.join(CONFIG['reports_directory'], filename)
        
        # Format full report with sources
        full_content = f"# {cmd.title}\n\n"
        full_content += f"*Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
        full_content += cmd.content
        full_content += format_sources()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_content)
        
        report = {
            "title": cmd.title,
            "content": cmd.content,
            "confidence": cmd.confidence,
            "sources_count": len(context["sources"]),
            "word_count": len(cmd.content.split()),
            "filepath": filepath,
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"📄 [bold blue]Report Created:[/bold blue] {cmd.title}")
        print(f"📊 Words: {report['word_count']}, Sources: {report['sources_count']}")
        print(f"💾 Saved: {filepath}")
        print(f"📈 Confidence: {cmd.confidence}")
        
        return report
    
    elif isinstance(cmd, ReportCompletion):
        print(f"\n✅ [bold green]RESEARCH COMPLETED[/bold green]")
        print(f"📋 Status: {cmd.status}")
        
        if cmd.completed_steps:
            print(f"📝 [bold]Completed steps:[/bold]")
            for step in cmd.completed_steps:
                print(f"   • {step}")
        
        return {
            "tool": "report_completion",
            "status": cmd.status,
            "completed_steps": cmd.completed_steps
        }
    
    else:
        return f"Unknown command: {type(cmd)}"

# =============================================================================
# MAIN EXECUTION ENGINE
# =============================================================================

def execute_research_task(task: str) -> str:
    """Execute research task using SGR"""
    
    print(Panel(task, title="🔍 Research Task", title_align="left"))
    
    # Detect language and setup
    language = detect_language(task)
    system_prompt = get_system_prompt(language)
    
    print(f"\n[bold green]🚀 SGR RESEARCH STARTED[/bold green]")
    print(f"[dim]🤖 Model: {CONFIG['openai_model']}[/dim]")
    print(f"[dim]🔗 Base URL: {CONFIG['openai_base_url'] or 'default'}[/dim]")
    print(f"[dim]🔑 API Key: {'✓ Configured' if CONFIG['openai_api_key'] else '✗ Missing'}[/dim]")
    print(f"[dim]📊 Max tokens: {CONFIG['max_tokens']}, Temperature: {CONFIG['temperature']}[/dim]")
    
    # Initialize conversation log
    log = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task}
    ]
    
    # Execute reasoning steps
    for i in range(CONFIG['max_execution_steps']):
        step_id = f"step_{i+1}"
        print(f"\n🧠 {step_id}: Planning next action...")
        
        # Add context about clarification usage to prevent cycling
        context_msg = ""
        if CONTEXT["clarification_used"]:
            context_msg = "IMPORTANT: Clarification already used. Do not request clarification again - proceed with available information."
        
        if context_msg:
            log.append({"role": "system", "content": context_msg})
        
        try:
            completion = client.beta.chat.completions.parse(
                model=CONFIG['openai_model'],
                response_format=NextStep,
                messages=log,
                max_tokens=CONFIG['max_tokens'],
                temperature=CONFIG['temperature']
            )
            
            job = completion.choices[0].message.parsed
            
            if job is None:
                print("[bold red]❌ Failed to parse LLM response[/bold red]")
                break
                
        except Exception as e:
            print(f"[bold red]❌ LLM request error: {str(e)}[/bold red]")
            break
        
        # Check for task completion
        if job.task_completed or isinstance(job.function, ReportCompletion):
            print(f"[bold green]✅ Task completed[/bold green]")
            dispatch(job.function, CONTEXT)
            break
        
        # Check for clarification cycling
        if isinstance(job.function, Clarification) and CONTEXT["clarification_used"]:
            print(f"[bold red]❌ Clarification cycling detected - forcing continuation[/bold red]")
            log.append({
                "role": "user", 
                "content": "ANTI-CYCLING: Clarification already used. Continue with generate_plan based on available information."
            })
            continue
        
        # Display current step
        next_step = job.remaining_steps[0] if job.remaining_steps else "Completing"
        print(f"[blue]{next_step}[/blue]")
        print(f"[dim]💭 Reasoning: {job.function.reasoning[:100]}...[/dim]")
        print(f"  Tool: {job.function.tool}")
        
        # Handle clarification specially
        if isinstance(job.function, Clarification):
            result = dispatch(job.function, CONTEXT)
            return "CLARIFICATION_NEEDED"
        
        # Add to conversation log
        log.append({
            "role": "assistant", 
            "content": next_step,
            "tool_calls": [{
                "type": "function",
                "id": step_id,
                "function": {
                    "name": job.function.tool,
                    "arguments": job.function.model_dump_json()
                }
            }]
        })
        
        # Execute tool
        result = dispatch(job.function, CONTEXT)
        
        # Add result to log
        result_text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        log.append({"role": "tool", "content": result_text, "tool_call_id": step_id})
        
        print(f"  Result: {result_text[:100]}..." if len(result_text) > 100 else f"  Result: {result_text}")
        
        # Auto-complete after report creation
        if isinstance(job.function, CreateReport):
            print(f"\n✅ [bold green]Auto-completing after report creation[/bold green]")
            break
    
    return "COMPLETED"

# =============================================================================
# MAIN INTERFACE
# =============================================================================

def main():
    """Main application interface"""
    print("[bold]🧠 SGR Research Agent - Adaptive Planning & Clarification[/bold]")
    print("Schema-Guided Reasoning with plan adaptation capabilities")
    print()
    print("Core features:")
    print("  🤔 Clarification-first approach")
    print("  🔄 Adaptive plan modification") 
    print("  📎 Automatic citation management")
    print("  🌍 Multi-language support")
    print()
    
    awaiting_clarification = False
    original_task = ""
    
    while True:
        try:
            print("=" * 60)
            if awaiting_clarification:
                response = input("💬 Your clarification response (or 'quit'): ").strip()
                awaiting_clarification = False
                
                if response.lower() in ['quit', 'exit']:
                    break
                
                # Combine original task with clarification
                task = f"Original request: '{original_task}'\nClarification: {response}\n\nProceed with research based on clarification."
                
                # Reset clarification flag for new combined task
                CONTEXT["clarification_used"] = False
            else:
                task = input("🔍 Enter research task (or 'quit'): ").strip()
            
            if task.lower() in ['quit', 'exit']:
                print("👋 Goodbye!")
                break
                
            if not task:
                print("❌ Empty task. Try again.")
                continue
            
            # Reset context for new task (except during clarification)
            if not awaiting_clarification:
                CONTEXT.clear()
                CONTEXT.update({
                    "plan": None,
                    "searches": [],
                    "sources": {},
                    "citation_counter": 0,
                    "clarification_used": False
                })
                original_task = task
            
            result = execute_research_task(task)
            
            if result == "CLARIFICATION_NEEDED":
                awaiting_clarification = True
                continue
            
            # Show statistics
            searches_count = len(CONTEXT.get("searches", []))
            sources_count = len(CONTEXT.get("sources", {}))
            print(f"\n📊 Session stats: 🔍 {searches_count} searches, 📎 {sources_count} sources")
            print(f"📁 Reports saved to: ./{CONFIG['reports_directory']}/")
            
        except KeyboardInterrupt:
            print("\n👋 Interrupted by user.")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            continue

if __name__ == "__main__":
    main()