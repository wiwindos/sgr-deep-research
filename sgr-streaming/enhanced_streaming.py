#!/usr/bin/env python3
"""
Enhanced Streaming Visualization for SGR JSON Schemas
Enhanced JSON schema streaming visualization with animations and detailed metrics
"""

import json
import time
import re
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, MofNCompleteColumn
from rich.tree import Tree
from rich.syntax import Syntax
from rich.columns import Columns
from rich.box import ROUNDED, DOUBLE, HEAVY
from rich.align import Align
from rich.padding import Padding

@dataclass
class StreamingMetrics:
    """Streaming metrics for detailed analysis"""
    start_time: float
    total_chars: int = 0
    total_chunks: int = 0
    json_parsing_attempts: int = 0
    successful_parses: int = 0
    field_completions: Dict[str, float] = None
    schema_detection_time: float = 0
    first_content_time: float = 0
    completion_time: float = 0
    
    def __post_init__(self):
        if self.field_completions is None:
            self.field_completions = {}
    
    @property
    def elapsed_time(self) -> float:
        return time.time() - self.start_time
    
    @property
    def chars_per_second(self) -> float:
        elapsed = self.elapsed_time
        return self.total_chars / elapsed if elapsed > 0 else 0
    
    @property
    def chunks_per_second(self) -> float:
        elapsed = self.elapsed_time
        return self.total_chunks / elapsed if elapsed > 0 else 0

class EnhancedSchemaParser:
    """Enhanced schema parser with animations and detailed metrics"""
    
    def __init__(self, console: Console):
        self.console = console
        self.current_json = ""
        self.parsed_fields = {}
        self.schema_type = None
        self.metrics = StreamingMetrics(start_time=time.time())
        self.field_progress = {}
        self.field_timing = {}  # Track start/end time for each field
        self.field_durations = {}  # Store completed field durations
        self.animation_frame = 0
        
        # Схемы полей для разных типов
        self.schema_fields = {
            "clarification": ["tool", "reasoning", "unclear_terms", "assumptions", "questions"],
            "generate_plan": ["tool", "reasoning", "research_goal", "planned_steps", "search_strategies"],
            "web_search": ["tool", "reasoning", "query", "max_results", "scrape_content"],
            "create_report": ["tool", "reasoning", "title", "content", "confidence"],
            "next_step": ["reasoning_steps", "current_situation", "plan_status", "searches_done", "enough_data", "remaining_steps", "task_completed", "function"]
        }
        
        # Эмодзи для разных типов полей
        self.field_emojis = {
            "tool": "🔧",
            "reasoning": "🧠",
            "reasoning_steps": "🧩",
            "current_situation": "📊",
            "query": "🔍",
            "research_goal": "🎯",
            "title": "📋",
            "content": "📝",
            "questions": "❓",
            "unclear_terms": "🤔",
            "planned_steps": "📋",
            "remaining_steps": "📅",
            "confidence": "📈",
            "searches_done": "🔎",
            "enough_data": "✅"
        }
    
    def detect_schema_type(self, json_content: str) -> str:
        """Определяет тип схемы с улучшенным детектированием"""
        if '"tool":"clarification"' in json_content:
            return "clarification"
        elif '"tool":"generate_plan"' in json_content:
            return "generate_plan"
        elif '"tool":"web_search"' in json_content:
            return "web_search"
        elif '"tool":"create_report"' in json_content:
            return "create_report"
        elif '"reasoning_steps"' in json_content:
            return "next_step"
        else:
            return "unknown"
    
    def get_field_progress(self, field_name: str, json_content: str) -> float:
        """Вычисляет прогресс заполнения поля (0.0 - 1.0)"""
        if field_name not in json_content:
            return 0.0
        
        # Ищем начало поля
        field_start = json_content.find(f'"{field_name}"')
        if field_start == -1:
            return 0.0
        
        # Ищем значение поля
        colon_pos = json_content.find(':', field_start)
        if colon_pos == -1:
            return 0.1  # Нашли название поля
        
        # Определяем тип значения
        value_start = json_content.find('"', colon_pos)
        if value_start == -1:
            # Возможно числовое или булево значение
            return 0.5
        
        # Ищем закрывающую кавычку или скобку
        if json_content[value_start:value_start+1] == '"':
            # Строковое значение
            closing_quote = json_content.find('"', value_start + 1)
            if closing_quote == -1:
                return 0.7  # Значение началось, но не закончилось
            else:
                return 1.0  # Значение завершено
        elif '[' in json_content[colon_pos:colon_pos+20]:
            # Массив
            bracket_start = json_content.find('[', colon_pos)
            bracket_end = json_content.find(']', bracket_start)
            if bracket_end == -1:
                return 0.8  # Массив начался, но не закончился
            else:
                return 1.0  # Массив завершен
        
        return 0.5
    
    def create_animated_progress_bar(self, progress: float, width: int = 20) -> str:
        """Создает анимированный прогресс-бар"""
        filled = int(progress * width)
        bar = ""
        
        # Анимированная заливка
        for i in range(width):
            if i < filled:
                bar += "█"
            elif i == filled and progress < 1.0:
                # Анимированный символ на границе
                animation_chars = ["▏", "▎", "▍", "▌", "▋", "▊", "▉"]
                char_index = int((time.time() * 3) % len(animation_chars))
                bar += animation_chars[char_index]
            else:
                bar += "░"
        
        # Цветовое кодирование
        if progress < 0.3:
            return f"[red]{bar}[/red]"
        elif progress < 0.7:
            return f"[yellow]{bar}[/yellow]"
        else:
            return f"[green]{bar}[/green]"
    
    def create_schema_tree(self) -> Tree:
        """Создает дерево схемы с прогрессом полей"""
        if not self.schema_type or self.schema_type == "unknown":
            tree = Tree("🔍 [dim]Detecting schema...[/dim]")
            return tree
        
        # Заголовок дерева
        schema_title = self.schema_type.replace("_", " ").title()
        tree = Tree(f"🤖 [bold cyan]{schema_title}[/bold cyan]")
        
        # Добавляем поля схемы
        expected_fields = self.schema_fields.get(self.schema_type, [])
        
        for field in expected_fields:
            progress = self.get_field_progress(field, self.current_json)
            emoji = self.field_emojis.get(field, "📄")
            
            # Создаем узел поля
            progress_bar = self.create_animated_progress_bar(progress, 15)
            status = "✅" if progress >= 1.0 else "⏳" if progress > 0 else "⏸️"
            
            field_node = tree.add(f"{emoji} [bold]{field}[/bold] {progress_bar} {status}")
            
            # Добавляем значение если доступно
            if field in self.parsed_fields:
                value = self.parsed_fields[field]
                if isinstance(value, str) and len(value) > 0:
                    preview = value[:40] + "..." if len(value) > 40 else value
                    field_node.add(f"[dim]→ {preview}[/dim]")
                elif isinstance(value, list) and len(value) > 0:
                    field_node.add(f"[dim]→ {len(value)} items[/dim]")
                    for i, item in enumerate(value[:3]):  # Показываем первые 3 элемента
                        item_preview = str(item)[:30] + "..." if len(str(item)) > 30 else str(item)
                        field_node.add(f"[dim]  {i+1}. {item_preview}[/dim]")
                    if len(value) > 3:
                        field_node.add(f"[dim]  ... и еще {len(value)-3}[/dim]")
                elif isinstance(value, dict):
                    field_node.add(f"[dim]→ Object with {len(value)} keys[/dim]")
        
        return tree
    
    def create_metrics_panel(self) -> Panel:
        """Создает панель с детальными метриками"""
        metrics_table = Table(show_header=False, box=None, padding=(0, 1))
        metrics_table.add_column("Metric", style="cyan", width=12)
        metrics_table.add_column("Value", style="white")
        
        # Основные метрики
        elapsed = self.metrics.elapsed_time
        metrics_table.add_row("⏱️ Time", f"{elapsed:.1f}s")
        metrics_table.add_row("📊 Chars", f"{self.metrics.total_chars:,}")
        metrics_table.add_row("📦 Chunks", f"{self.metrics.total_chunks}")
        metrics_table.add_row("⚡ Speed", f"{self.metrics.chars_per_second:.0f} ch/s")
        
        # Прогресс парсинга
        if self.metrics.json_parsing_attempts > 0:
            parse_success_rate = self.metrics.successful_parses / self.metrics.json_parsing_attempts * 100
            metrics_table.add_row("🎯 Parse", f"{parse_success_rate:.1f}%")
        
        # Прогресс схемы
        if self.schema_type and self.schema_type != "unknown":
            expected_fields = self.schema_fields.get(self.schema_type, [])
            completed_fields = sum(1 for field in expected_fields if self.get_field_progress(field, self.current_json) >= 1.0)
            schema_progress = completed_fields / len(expected_fields) * 100 if expected_fields else 0
            metrics_table.add_row("📋 Schema", f"{completed_fields}/{len(expected_fields)} ({schema_progress:.0f}%)")
        
        return Panel(
            metrics_table,
            title="📊 Metrics",
            border_style="blue",
            box=ROUNDED
        )
    
    def create_json_preview(self) -> Panel:
        """Создает превью JSON с подсветкой синтаксиса"""
        if not self.current_json:
            return Panel(
                "[dim]Waiting for JSON content...[/dim]",
                title="📄 JSON Preview",
                border_style="dim"
            )
        
        # Берем последние 300 символов для превью
        preview_json = self.current_json[-300:] if len(self.current_json) > 300 else self.current_json
        
        # Добавляем индикатор если JSON обрезан
        if len(self.current_json) > 300:
            preview_json = "...\n" + preview_json
        
        try:
            # Пытаемся форматировать JSON для лучшего отображения
            if self.current_json.strip().endswith('}'):
                parsed = json.loads(self.current_json)
                formatted_json = json.dumps(parsed, indent=2, ensure_ascii=False)
                syntax = Syntax(formatted_json, "json", theme="monokai", line_numbers=False)
            else:
                syntax = Syntax(preview_json, "json", theme="monokai", line_numbers=False)
        except:
            # Если не удается распарсить, показываем как есть
            syntax = Text(preview_json, style="dim")
        
        return Panel(
            syntax,
            title="📄 JSON Preview",
            border_style="green" if self.current_json.strip().endswith('}') else "yellow",
            box=ROUNDED
        )
    
    def create_comprehensive_display(self) -> Group:
        """Создает комплексное отображение с деревом, метриками и превью"""
        
        # Заголовок с анимацией
        self.animation_frame += 1
        spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        spinner = spinner_chars[self.animation_frame % len(spinner_chars)]
        
        if self.current_json.strip().endswith('}'):
            title = f"✅ [bold green]Schema Generation Complete![/bold green]"
        else:
            title = f"{spinner} [bold cyan]Generating Schema...[/bold cyan]"
        
        # Создаем компоненты
        schema_tree = self.create_schema_tree()
        metrics_panel = self.create_metrics_panel()
        json_preview = self.create_json_preview()
        
        # Группируем в колонки
        top_row = Columns([
            Panel(schema_tree, title="🌳 Schema Progress", border_style="cyan", box=ROUNDED),
            metrics_panel
        ], equal=True)
        
        # Проверяем есть ли вопросы для clarification
        questions_panel = None
        if (self.schema_type == "clarification" and 
            "function" in self.parsed_fields and 
            "questions" in self.parsed_fields["function"] and 
            isinstance(self.parsed_fields["function"]["questions"], list)):
            
            questions = self.parsed_fields["function"]["questions"]
            if questions:
                questions_table = Table(show_header=False, box=None)
                questions_table.add_column("❓ Question", style="yellow", width=70)
                
                for i, q in enumerate(questions, 1):
                    questions_table.add_row(f"{i}. {q}")
                
                questions_panel = Panel(
                    questions_table,
                    title="❓ Clarification Questions",
                    border_style="yellow",
                    box=ROUNDED
                )
        
        # Собираем все вместе
        components = [
            Panel(title, box=HEAVY, border_style="cyan"),
            top_row,
            json_preview
        ]
        
        # Добавляем вопросы если есть
        if questions_panel:
            components.append(Text(""))  # Пустая строка для отступа
            components.append(questions_panel)
        
        return Group(*components)
    
    def update_from_stream_chunk(self, content_delta: str) -> Group:
        """Обновляет состояние на основе нового чанка и возвращает отображение"""
        self.current_json += content_delta
        self.metrics.total_chars += len(content_delta)
        self.metrics.total_chunks += 1
        
        # Записываем время первого контента
        if self.metrics.total_chars == len(content_delta):
            self.metrics.first_content_time = time.time()
        
        # Пытаемся определить схему
        if not self.schema_type or self.schema_type == "unknown":
            new_schema_type = self.detect_schema_type(self.current_json)
            if new_schema_type != "unknown":
                self.schema_type = new_schema_type
                self.metrics.schema_detection_time = time.time()
        
        # Пытаемся распарсить JSON
        self.metrics.json_parsing_attempts += 1
        try:
            if self.current_json.strip().endswith('}'):
                parsed = json.loads(self.current_json)
                self.parsed_fields = parsed
                self.metrics.successful_parses += 1
                self.metrics.completion_time = time.time()
            else:
                # Частичный парсинг
                self._partial_parse()
        except:
            pass
        
        return self.create_comprehensive_display()
    
    def _partial_parse(self):
        """Частичный парсинг JSON для извлечения доступных полей"""
        # Извлекаем простые поля
        patterns = {
            'string': r'"([^"]+)"\s*:\s*"([^"]*)"',
            'number': r'"([^"]+)"\s*:\s*(\d+(?:\.\d+)?)',
            'boolean': r'"([^"]+)"\s*:\s*(true|false)',
        }
        
        for pattern_type, pattern in patterns.items():
            matches = re.findall(pattern, self.current_json)
            for field_name, value in matches:
                # Track field timing
                current_time = time.time()
                if field_name not in self.field_timing:
                    self.field_timing[field_name] = {'start': current_time}
                
                if pattern_type == 'number':
                    try:
                        self.parsed_fields[field_name] = float(value) if '.' in value else int(value)
                    except:
                        self.parsed_fields[field_name] = value
                elif pattern_type == 'boolean':
                    self.parsed_fields[field_name] = value.lower() == 'true'
                else:
                    self.parsed_fields[field_name] = value
        
        # Извлекаем массивы
        array_pattern = r'"([^"]+)"\s*:\s*\[(.*?)\]'
        array_matches = re.findall(array_pattern, self.current_json, re.DOTALL)
        for field_name, array_content in array_matches:
            # Track field timing
            current_time = time.time()
            if field_name not in self.field_timing:
                self.field_timing[field_name] = {'start': current_time}
            
            # Простое извлечение элементов массива
            items = re.findall(r'"([^"]*)"', array_content)
            if items:
                self.parsed_fields[field_name] = items
    
    def finalize_field_timings(self):
        """Finalize timing for all fields that have been started"""
        current_time = time.time()
        
        # Calculate field durations differently - based on when field was detected
        # This gives us the time from start of parsing to when each field appeared
        for field_name, timing in self.field_timing.items():
            if 'end' not in timing:
                # Duration is from parsing start to when field was first detected
                self.field_durations[field_name] = timing['start'] - self.metrics.start_time

def enhanced_streaming_display(stream, operation_name: str, console: Console) -> Tuple[Any, str, Dict]:
    """
    Улучшенное отображение стриминга с детальными метриками и анимациями
    
    Args:
        stream: OpenAI streaming объект
        operation_name: Название операции
        console: Rich console
    
    Returns:
        tuple: (final_response, accumulated_content, metrics_dict)
    """
    
    # Print a separator to distinguish schema generation from dashboard
    console.print("\n" + "─" * 80, style="dim")
    console.print(f"🎯 [bold cyan]Starting {operation_name}...[/bold cyan]", justify="center")
    console.print("─" * 80 + "\n", style="dim")
    
    parser = EnhancedSchemaParser(console)
    accumulated_content = ""
    
    # Создаем layout для живого отображения
    layout = Layout()
    
    with Live(layout, console=console, refresh_per_second=8, auto_refresh=True, transient=False) as live:
        try:
            for chunk in stream:
                # Извлекаем содержимое чанка
                content_delta = None
                
                if hasattr(chunk, 'type') and chunk.type == 'content.delta':
                    content_delta = chunk.delta
                elif hasattr(chunk, 'choices') and chunk.choices:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        content_delta = delta.content
                
                if content_delta:
                    accumulated_content += content_delta
                    
                    # Обновляем отображение
                    display = parser.update_from_stream_chunk(content_delta)
                    layout.update(display)
            
            # Получаем финальный ответ
            final_response = stream.get_final_completion()
            
            # Финальное обновление с завершенным статусом
            if accumulated_content:
                final_display = parser.update_from_stream_chunk("")  # Триггерим финальное обновление
                layout.update(final_display)
            
            # Показываем результат еще 1 секунду
            time.sleep(1.0)
            
        except Exception as e:
            error_panel = Panel(
                f"❌ [bold red]Streaming Error:[/bold red]\n{str(e)}",
                title="Error",
                border_style="red",
                box=HEAVY
            )
            layout.update(error_panel)
            time.sleep(3.0)
            raise
    
    # Собираем финальные метрики
    # Finalize field timings
    parser.finalize_field_timings()
    
    metrics_dict = {
        "total_time": parser.metrics.elapsed_time,
        "total_chars": parser.metrics.total_chars,
        "total_chunks": parser.metrics.total_chunks,
        "chars_per_second": parser.metrics.chars_per_second,
        "chunks_per_second": parser.metrics.chunks_per_second,
        "schema_type": parser.schema_type,
        "successful_parses": parser.metrics.successful_parses,
        "parse_attempts": parser.metrics.json_parsing_attempts,
        "schema_detection_time": parser.metrics.schema_detection_time - parser.metrics.start_time if parser.metrics.schema_detection_time > 0 else 0,
        "first_content_time": parser.metrics.first_content_time - parser.metrics.start_time if parser.metrics.first_content_time > 0 else 0,
        "field_durations": parser.field_durations  # Add field timing data
    }
    
    # Добавляем отступ перед финальной сводкой
    console.print("")  # Пустая строка для отступа
    
    # Показываем компактную финальную сводку
    _show_compact_summary(console, operation_name, parser.schema_type, metrics_dict)
    
    # Add separator to mark end of schema generation
    console.print("\n" + "─" * 80, style="dim")
    console.print(f"✅ [bold green]{operation_name} Complete![/bold green]", justify="center")
    console.print("─" * 80 + "\n", style="dim")
    
    return final_response, accumulated_content, metrics_dict

def _show_compact_summary(console: Console, operation_name: str, schema_type: str, metrics: dict):
    """Показывает компактную сводку без больших отступов"""
    
    # Создаем компактную таблицу результатов
    summary_table = Table(show_header=False, box=None, padding=(0, 1))
    summary_table.add_column("", style="bold", width=12)
    summary_table.add_column("", style="white", width=25)
    summary_table.add_column("", style="dim", width=15)
    
    summary_table.add_row(
        f"✅ {operation_name}",
        f"Schema: {schema_type or 'unknown'}",
        f"{metrics.get('chars_per_second', 0):.0f} ch/s"
    )
    
    # Компактная панель без больших отступов
    compact_panel = Panel(
        summary_table,
        title="🎯 Completed",
        title_align="left",
        border_style="green",
        box=ROUNDED,
        expand=False,  # Не расширяем на всю ширину
        width=60       # Фиксированная ширина
    )
    
    console.print(compact_panel)


# Пример специализированных отображений для разных схем
class SpecializedDisplays:
    """Специализированные отображения для разных типов схем"""
    
    @staticmethod
    def create_clarification_display(parsed_fields: Dict) -> Panel:
        """Специальное отображение для clarification схемы"""
        content = []
        
        if "unclear_terms" in parsed_fields:
            terms_text = Text("🤔 Unclear terms: ", style="bold yellow")
            terms_text.append(", ".join(parsed_fields["unclear_terms"]), style="yellow")
            content.append(terms_text)
        
        if "questions" in parsed_fields:
            questions_table = Table(show_header=False, box=None)
            questions_table.add_column("Q", style="cyan", width=60)
            for i, q in enumerate(parsed_fields["questions"], 1):
                questions_table.add_row(f"{i}. {q}")
            content.append(questions_table)
        
        return Panel(
            Group(*content) if content else "[dim]Preparing clarification...[/dim]",
            title="❓ Clarification Request",
            border_style="yellow",
            box=DOUBLE
        )
    
    @staticmethod
    def create_search_display(parsed_fields: Dict) -> Panel:
        """Специальное отображение для web_search схемы"""
        if "query" in parsed_fields:
            query_text = Text("🔍 Search Query: ", style="bold cyan")
            query_text.append(parsed_fields["query"], style="white")
            
            return Panel(
                query_text,
                title="🔍 Web Search",
                border_style="cyan",
                box=ROUNDED
            )
        
        return Panel(
            "[dim]Preparing search query...[/dim]",
            title="🔍 Web Search",
            border_style="dim"
        )
    
    @staticmethod
    def create_report_display(parsed_fields: Dict) -> Panel:
        """Специальное отображение для create_report схемы"""
        content = []
        
        if "title" in parsed_fields:
            title_text = Text("📋 Title: ", style="bold green")
            title_text.append(parsed_fields["title"], style="white")
            content.append(title_text)
        
        if "confidence" in parsed_fields:
            conf_text = Text("📈 Confidence: ", style="bold blue")
            conf_text.append(str(parsed_fields["confidence"]), style="blue")
            content.append(conf_text)
        
        if "content" in parsed_fields:
            word_count = len(parsed_fields["content"].split())
            content_text = Text("📝 Content: ", style="bold cyan")
            content_text.append(f"{word_count} words", style="cyan")
            content.append(content_text)
        
        return Panel(
            Group(*content) if content else "[dim]Preparing report...[/dim]",
            title="📝 Research Report",
            border_style="green",
            box=DOUBLE
        )
