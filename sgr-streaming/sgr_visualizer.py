#!/usr/bin/env python3
"""
SGR Process Visualizer
Визуализатор процесса Schema-Guided Reasoning с красивыми интерактивными элементами
"""

import time
from typing import Dict, List, Any, Optional
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, MofNCompleteColumn
from rich.columns import Columns
from rich.box import ROUNDED, DOUBLE, HEAVY, SIMPLE
from rich.align import Align
from rich.padding import Padding
from rich.layout import Layout
from rich.live import Live

class SGRProcessVisualizer:
    """Визуализатор SGR процесса с интерактивными элементами"""
    
    def __init__(self, console: Console):
        self.console = console
        self.step_counter = 0
        self.completed_steps = []
        self.current_step = None
        self.context_info = {}
        
        # SGR этапы и их описания
        self.sgr_stages = {
            "schema_generation": {
                "emoji": "🧠",
                "name": "Schema Generation",
                "description": "LLM reasoning and schema generation",
                "color": "magenta"
            },
            "clarification": {
                "emoji": "❓",
                "name": "Clarification",
                "description": "Asking clarifying questions",
                "color": "yellow"
            },
            "generate_plan": {
                "emoji": "📋",
                "name": "Plan Generation", 
                "description": "Creating research strategy",
                "color": "cyan"
            },
            "web_search": {
                "emoji": "🔍",
                "name": "Web Search",
                "description": "Gathering information",
                "color": "blue"
            },
            "adapt_plan": {
                "emoji": "🔄",
                "name": "Plan Adaptation",
                "description": "Adjusting strategy",
                "color": "magenta"
            },
            "create_report": {
                "emoji": "📝",
                "name": "Report Creation",
                "description": "Writing final report",
                "color": "green"
            },
            "report_completion": {
                "emoji": "✅",
                "name": "Completion",
                "description": "Task finished",
                "color": "bold green"
            }
        }
    
    def update_context(self, context: Dict[str, Any]):
        """Обновляет контекстную информацию"""
        self.context_info.update(context)
    
    def start_step(self, step_name: str, details: Optional[str] = None):
        """Начинает новый этап SGR"""
        self.step_counter += 1
        self.current_step = {
            "name": step_name,
            "details": details,
            "start_time": time.time(),
            "step_id": self.step_counter
        }
    
    def complete_step(self, result: Any = None):
        """Завершает текущий этап"""
        if self.current_step:
            self.current_step["end_time"] = time.time()
            self.current_step["duration"] = self.current_step["end_time"] - self.current_step["start_time"]
            self.current_step["result"] = result
            self.completed_steps.append(self.current_step)
            self.current_step = None
    
    def create_sgr_pipeline_view(self) -> Panel:
        """Creates SGR pipeline visualization"""
        
        # Create stages table
        stages_table = Table(show_header=True, header_style="bold cyan", box=SIMPLE)
        stages_table.add_column("Stage", style="cyan", width=18)
        stages_table.add_column("Status", justify="center", width=8)
        stages_table.add_column("Progress", width=15)
        stages_table.add_column("Time", justify="right", width=8)
        
        # Use step_tracker data if available, otherwise fallback to internal tracking
        if hasattr(self, 'step_tracker') and self.step_tracker:
            completed_steps = [s for s in self.step_tracker.steps if s.is_completed]
            current_step = self.step_tracker.current_step
            
            # Group steps by type and calculate timing data
            step_timing = {}
            total_time = 0.0
            completed_stage_names = []
            
            for step in completed_steps:
                # Extract base tool name (remove _step_X suffix)
                base_name = step.name.split('_step_')[0] if '_step_' in step.name else step.name
                
                # Sum times for the same tool type
                if base_name in step_timing:
                    step_timing[base_name] += step.duration
                else:
                    step_timing[base_name] = step.duration
                    completed_stage_names.append(base_name)
                
                total_time += step.duration
            
            # Handle current step
            current_stage = None
            if current_step and current_step.start_time:
                current_duration = time.time() - current_step.start_time
                total_time += current_duration
                
                # Extract base name for current step
                current_stage = current_step.name.split('_step_')[0] if '_step_' in current_step.name else current_step.name
            

        else:
            # Fallback to internal tracking
            completed_stage_names = [step["name"] for step in self.completed_steps]
            current_stage = self.current_step["name"] if self.current_step else None
            step_timing = {step["name"]: step["duration"] for step in self.completed_steps}
            total_time = sum(step_timing.values())
        
        for stage_key, stage_info in self.sgr_stages.items():
            emoji = stage_info["emoji"]
            name = stage_info["name"]
            color = stage_info["color"]
            
            # Determine status using step_timing data
            if stage_key in completed_stage_names:
                status = "✅"
                progress = "[green]████████████████[/green]"
                # Get timing from step_timing mapping
                duration = step_timing.get(stage_key, 0)
                time_text = f"{duration:.1f}s"
            elif stage_key == current_stage:
                status = "🔄"
                progress = "[yellow]████████░░░░░░░░[/yellow]"
                # Show current execution time
                if hasattr(self, 'step_tracker') and self.step_tracker and self.step_tracker.current_step:
                    current_duration = self.step_tracker.current_step.duration
                    time_text = f"{current_duration:.1f}s"
                elif self.current_step:
                    current_duration = time.time() - self.current_step["start_time"]
                    time_text = f"{current_duration:.1f}s"
                else:
                    time_text = "..."
            else:
                status = "⏸️"
                progress = "[dim]░░░░░░░░░░░░░░░░[/dim]"
                time_text = "-"
            
            stages_table.add_row(
                f"[{color}]{emoji} {name}[/{color}]",
                status,
                progress,
                time_text
            )
        
        return Panel(
            stages_table,
            title=f"🚀 SGR Pipeline (Total: {total_time:.1f}s)",
            border_style="cyan",
            box=ROUNDED
        )
    
    def create_context_panel(self) -> Panel:
        """Создает панель с контекстной информацией"""
        
        context_table = Table(show_header=False, box=None, padding=(0, 1))
        context_table.add_column("Key", style="cyan", width=15)
        context_table.add_column("Value", style="white")
        
        # Основная информация о задаче
        if "task" in self.context_info:
            task_preview = self.context_info["task"][:50] + "..." if len(self.context_info["task"]) > 50 else self.context_info["task"]
            context_table.add_row("🎯 Task", task_preview)
        
        # Информация о плане
        if "plan" in self.context_info and self.context_info["plan"]:
            plan = self.context_info["plan"]
            if "research_goal" in plan:
                goal_preview = plan["research_goal"][:40] + "..." if len(plan["research_goal"]) > 40 else plan["research_goal"]
                context_table.add_row("📋 Goal", goal_preview)
            
            if "planned_steps" in plan:
                context_table.add_row("📝 Steps", f"{len(plan['planned_steps'])} planned")
        
        # Информация о поиске
        if "searches" in self.context_info:
            searches_count = len(self.context_info["searches"])
            context_table.add_row("🔍 Searches", f"{searches_count} completed")
        
        # Информация об источниках
        if "sources" in self.context_info:
            sources_count = len(self.context_info["sources"])
            context_table.add_row("📎 Sources", f"{sources_count} collected")
        
        # Статистика времени
        total_time = sum(step.get("duration", 0) for step in self.completed_steps)
        if total_time > 0:
            context_table.add_row("⏱️ Total Time", f"{total_time:.1f}s")
        
        return Panel(
            context_table,
            title="📊 Context",
            border_style="blue",
            box=ROUNDED
        )
    
    def create_current_activity(self) -> Panel:
        """Создает панель текущей активности"""
        
        if not self.current_step:
            return Panel(
                Align.center("🏁 [bold green]All steps completed![/bold green]"),
                title="🔄 Current Activity",
                border_style="green",
                box=ROUNDED
            )
        
        step_name = self.current_step["name"]
        stage_info = self.sgr_stages.get(step_name, {})
        emoji = stage_info.get("emoji", "⚙️")
        name = stage_info.get("name", step_name)
        description = stage_info.get("description", "Processing...")
        
        # Вычисляем время выполнения
        elapsed = time.time() - self.current_step["start_time"]
        
        # Создаем контент
        activity_text = Text()
        activity_text.append(f"{emoji} ", style="bold")
        activity_text.append(f"{name}\n", style="bold cyan")
        activity_text.append(f"{description}\n", style="dim")
        activity_text.append(f"⏱️ Running for {elapsed:.1f}s", style="yellow")
        
        # Добавляем детали если есть
        if self.current_step.get("details"):
            activity_text.append(f"\n💭 {self.current_step['details']}", style="dim white")
        
        return Panel(
            Align.center(activity_text),
            title="🔄 Current Activity",
            border_style="yellow",
            box=ROUNDED
        )
    
    def create_step_history_tree(self) -> Panel:
        """Создает дерево истории выполненных шагов"""
        
        if not self.completed_steps:
            tree = Tree("📝 [dim]No completed steps yet[/dim]")
        else:
            tree = Tree("📝 [bold]Execution History[/bold]")
            
            for i, step in enumerate(self.completed_steps, 1):
                step_name = step["name"]
                duration = step.get("duration", 0)
                stage_info = self.sgr_stages.get(step_name, {})
                emoji = stage_info.get("emoji", "⚙️")
                
                step_node = tree.add(f"{emoji} [bold]{stage_info.get('name', step_name)}[/bold] ({duration:.1f}s)")
                
                # Добавляем детали результата
                result = step.get("result")
                if isinstance(result, dict):
                    if "query" in result:  # Поиск
                        step_node.add(f"🔍 Query: {result['query'][:40]}...")
                    elif "research_goal" in result:  # План
                        step_node.add(f"🎯 Goal: {result['research_goal'][:40]}...")
                    elif "title" in result:  # Отчет
                        step_node.add(f"📄 Title: {result['title'][:40]}...")
                elif isinstance(result, str) and len(result) > 0:
                    preview = result[:50] + "..." if len(result) > 50 else result
                    step_node.add(f"📋 {preview}")
        
        return Panel(
            tree,
            title="📚 History",
            border_style="magenta",
            box=ROUNDED
        )
    
    def create_field_timing_panel(self) -> Panel:
        """Creates a panel showing field generation timing for current or last schema step"""
        
        # Find the most recent step with field_durations
        target_step = None
        if hasattr(self, 'step_tracker') and self.step_tracker:
            # Check current step first
            if (self.step_tracker.current_step and 
                self.step_tracker.current_step.field_durations):
                target_step = self.step_tracker.current_step
            else:
                # Check completed steps in reverse order
                for step in reversed(self.step_tracker.steps):
                    if step.is_completed and step.field_durations:
                        target_step = step
                        break
        
        if not target_step or not target_step.field_durations:
            return Panel(
                "[dim]No field timing data available[/dim]",
                title="⏱️ Schema Field Timing",
                border_style="dim",
                box=ROUNDED
            )
        
        # Create timing table
        timing_table = Table(show_header=True, header_style="bold cyan", box=SIMPLE)
        timing_table.add_column("Field", style="cyan", width=20)
        timing_table.add_column("Time", justify="right", width=10)
        timing_table.add_column("Progress", width=15)
        
        # Sort fields by duration (longest first)
        sorted_fields = sorted(
            target_step.field_durations.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        max_time = max(target_step.field_durations.values()) if target_step.field_durations else 1.0
        
        for field_name, duration in sorted_fields:
            # Create progress bar based on relative time
            progress_ratio = duration / max_time if max_time > 0 else 0
            progress_blocks = int(progress_ratio * 10)
            progress_bar = "█" * progress_blocks + "░" * (10 - progress_blocks)
            
            # Format field name nicely
            display_name = field_name.replace('_', ' ').title()
            if len(display_name) > 18:
                display_name = display_name[:15] + "..."
            
            timing_table.add_row(
                display_name,
                f"{duration:.2f}s",
                f"[cyan]{progress_bar}[/cyan]"
            )
        
        # Add summary row with step total time
        step_total_time = target_step.duration
        timing_table.add_row(
            "[bold]Step Total[/bold]",
            f"[bold]{step_total_time:.2f}s[/bold]",
            "[bold cyan]██████████[/bold cyan]"
        )
        
        step_name = target_step.name.split('_step_')[0] if '_step_' in target_step.name else target_step.name
        step_status = "Current" if target_step == getattr(self.step_tracker, 'current_step', None) else "Last"
        
        return Panel(
            timing_table,
            title=f"⏱️ Field Generation Order ({step_status}: {step_name})",
            border_style="yellow",
            box=ROUNDED
        )
    
    def create_comprehensive_dashboard(self) -> Group:
        """Создает комплексную панель мониторинга SGR процесса"""
        
        # Верхний ряд - главная информация: пайплайн и контекст  
        top_row = Columns([
            self.create_sgr_pipeline_view(),
            self.create_context_panel()
        ], equal=True)
        
        # Средний ряд - текущая активность (компактно)
        middle_row = self.create_current_activity()
        
        # Нижний ряд - детальная информация: история и field timing
        bottom_row = Columns([
            self.create_step_history_tree(),
            self.create_field_timing_panel()
        ], equal=True)
        
        return Group(
            top_row,
            middle_row,
            bottom_row
        )
    
    def show_step_transition(self, from_step: str, to_step: str, reason: str = ""):
        """Показывает красивый переход между этапами"""
        
        from_info = self.sgr_stages.get(from_step, {})
        to_info = self.sgr_stages.get(to_step, {})
        
        transition_text = Text()
        transition_text.append(f"{from_info.get('emoji', '⚙️')} {from_info.get('name', from_step)}", style=f"bold {from_info.get('color', 'white')}")
        transition_text.append(" → ", style="dim")
        transition_text.append(f"{to_info.get('emoji', '⚙️')} {to_info.get('name', to_step)}", style=f"bold {to_info.get('color', 'white')}")
        
        if reason:
            transition_text.append(f"\n💭 {reason}", style="dim italic")
        
        panel = Panel(
            Align.center(transition_text),
            title="🔄 Step Transition",
            border_style="cyan",
            box=DOUBLE
        )
        
        self.console.print(panel)
        time.sleep(0.5)  # Небольшая пауза для эффекта

class SGRLiveMonitor:
    """Живой монитор SGR процесса с автообновлением"""
    
    def __init__(self, console: Console, step_tracker=None):
        self.console = console
        self.visualizer = SGRProcessVisualizer(console)
        if step_tracker:
            self.visualizer.step_tracker = step_tracker
        self.live = None
        self.is_running = False
    
    def start_monitoring(self):
        """Запускает живой мониторинг"""
        if self.is_running:
            return
        
        self.is_running = True
        layout = Layout()
        
        self.live = Live(
            layout, 
            console=self.console, 
            refresh_per_second=4,
            screen=False,
            auto_refresh=True,
            transient=False
        )
        self.live.start()
        
        # Обновляем отображение
        self.update_display()
    
    def stop_monitoring(self):
        """Останавливает мониторинг"""
        if self.live and self.is_running:
            self.live.stop()
            self.is_running = False
            
            # Показываем компактную финальную сводку
            self._show_final_summary()
    
    def update_display(self):
        """Обновляет отображение"""
        if self.live and self.is_running:
            dashboard = self.visualizer.create_comprehensive_dashboard()
            self.live.update(dashboard)
    
    def start_step(self, step_name: str, details: Optional[str] = None):
        """Начинает новый этап с обновлением отображения"""
        # Избегаем дублирования этапов планирования
        if step_name != "planning":
            self.visualizer.start_step(step_name, details)
            self.update_display()
    
    def complete_step(self, result: Any = None):
        """Завершает этап с обновлением отображения"""
        # Завершаем только если есть текущий этап (не планирование)
        if self.visualizer.current_step:
            self.visualizer.complete_step(result)
            self.update_display()
    
    def update_context(self, context: Dict[str, Any]):
        """Обновляет контекст с обновлением отображения"""
        self.visualizer.update_context(context)
        self.update_display()
    
    def show_transition(self, from_step: str, to_step: str, reason: str = ""):
        """Показывает переход между этапами"""
        self.visualizer.show_step_transition(from_step, to_step, reason)
    
    def _show_final_summary(self):
        """Показывает компактную финальную сводку"""
        if not self.visualizer.completed_steps:
            return
        
        # Подсчитываем статистику
        total_time = sum(step.get("duration", 0) for step in self.visualizer.completed_steps)
        total_steps = len(self.visualizer.completed_steps)
        
        # Создаем компактную таблицу
        summary_table = Table(show_header=False, box=None, padding=(0, 1))
        summary_table.add_column("", style="bold", width=15)
        summary_table.add_column("", style="white", width=20)
        summary_table.add_column("", style="dim", width=15)
        
        summary_table.add_row(
            "🏁 SGR Complete",
            f"{total_steps} steps",
            f"{total_time:.1f}s total"
        )
        
        # Последний выполненный шаг
        if self.visualizer.completed_steps:
            last_step = self.visualizer.completed_steps[-1]
            step_name = last_step.get("name", "unknown")
            stage_info = self.visualizer.sgr_stages.get(step_name, {})
            emoji = stage_info.get("emoji", "⚙️")
            name = stage_info.get("name", step_name)
            
            summary_table.add_row(
                f"{emoji} Final Step",
                name,
                f"{last_step.get('duration', 0):.1f}s"
            )
        
        # Компактная панель
        compact_panel = Panel(
            summary_table,
            title="📊 SGR Summary",
            title_align="left", 
            border_style="green",
            box=ROUNDED,
            expand=False,
            width=55
        )
        
        self.console.print(compact_panel)

# Пример использования
def demo_sgr_visualization():
    """Демонстрация SGR визуализации"""
    console = Console()
    monitor = SGRLiveMonitor(console)
    
    try:
        # Запускаем мониторинг
        monitor.start_monitoring()
        
        # Обновляем контекст
        monitor.update_context({
            "task": "Исследование цен на BMW X6 2025 года в России",
            "plan": {
                "research_goal": "Найти актуальные цены на BMW X6",
                "planned_steps": ["Поиск официальных данных", "Анализ дилеров", "Сравнение цен"]
            },
            "searches": [],
            "sources": {}
        })
        
        # Симулируем этапы SGR
        steps = [
            ("generate_plan", "Создание плана исследования"),
            ("web_search", "Поиск информации о ценах"),
            ("web_search", "Дополнительный поиск по дилерам"),
            ("create_report", "Составление итогового отчета"),
            ("report_completion", "Завершение задачи")
        ]
        
        for i, (step_name, details) in enumerate(steps):
            monitor.start_step(step_name, details)
            time.sleep(2)  # Симуляция работы
            
            # Симулируем результат
            result = f"Результат этапа {i+1}: {step_name}"
            monitor.complete_step(result)
            
            # Обновляем контекст
            if step_name == "web_search":
                current_searches = monitor.visualizer.context_info.get("searches", [])
                current_searches.append({"query": f"BMW X6 prices search {len(current_searches)+1}"})
                monitor.update_context({"searches": current_searches})
            
            time.sleep(1)
        
        # Показываем финальное состояние
        time.sleep(1)
        
    finally:
        monitor.stop_monitoring()

if __name__ == "__main__":
    demo_sgr_visualization()
