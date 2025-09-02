#!/usr/bin/env python3
"""
SGR Step Tracker
Трекер этапов SGR для правильного отображения хода выполнения
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import time

@dataclass
class SGRStep:
    """Этап SGR процесса"""
    name: str
    start_time: float
    end_time: Optional[float] = None
    result: Any = None
    details: Optional[str] = None
    field_durations: Optional[Dict[str, float]] = None  # Timing for schema fields
    
    @property
    def duration(self) -> float:
        """Длительность выполнения этапа"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    @property
    def is_completed(self) -> bool:
        """Завершен ли этап"""
        return self.end_time is not None

class SGRStepTracker:
    """Трекер этапов SGR для правильного мониторинга"""
    
    def __init__(self):
        self.steps: List[SGRStep] = []
        self.current_step: Optional[SGRStep] = None
        self.sgr_order = [
            "clarification",
            "generate_plan", 
            "web_search",
            "adapt_plan",
            "create_report",
            "report_completion"
        ]
    
    def start_step(self, step_name: str, details: Optional[str] = None):
        """Начинает новый этап SGR"""
        # Завершаем предыдущий этап если он есть
        if self.current_step and not self.current_step.is_completed:
            self.complete_current_step("Interrupted by new step")
        
        # Создаем новый этап
        step = SGRStep(
            name=step_name,
            start_time=time.time(),
            details=details
        )
        
        self.current_step = step
        self.steps.append(step)
    
    def complete_current_step(self, result: Any = None):
        """Завершает текущий этап"""
        if self.current_step and not self.current_step.is_completed:
            self.current_step.end_time = time.time()
            self.current_step.result = result
            self.current_step = None
    
    def update_field_durations(self, field_durations: Dict[str, float]):
        """Updates field durations for the current step"""
        if self.current_step:
            self.current_step.field_durations = field_durations
    
    def get_step_summary(self) -> Dict[str, Any]:
        """Возвращает сводку по этапам"""
        completed_steps = [s for s in self.steps if s.is_completed]
        total_time = sum(s.duration for s in completed_steps)
        
        # Подсчитываем этапы по типам
        step_counts = {}
        for step in completed_steps:
            step_counts[step.name] = step_counts.get(step.name, 0) + 1
        
        return {
            "total_steps": len(completed_steps),
            "total_time": total_time,
            "step_counts": step_counts,
            "current_step": self.current_step.name if self.current_step else None,
            "steps": completed_steps
        }
    
    def get_sgr_pipeline_status(self) -> Dict[str, str]:
        """Возвращает статус SGR пайплайна"""
        status = {}
        completed_step_names = {s.name for s in self.steps if s.is_completed}
        current_step_name = self.current_step.name if self.current_step else None
        
        for step_name in self.sgr_order:
            if step_name in completed_step_names:
                status[step_name] = "completed"
            elif step_name == current_step_name:
                status[step_name] = "in_progress"
            else:
                status[step_name] = "pending"
        
        return status
    
    def get_clean_history(self) -> List[Dict[str, Any]]:
        """Возвращает очищенную историю без дублирования"""
        clean_history = []
        
        # Группируем по типам этапов
        grouped_steps = {}
        for step in self.steps:
            if step.is_completed:
                if step.name not in grouped_steps:
                    grouped_steps[step.name] = []
                grouped_steps[step.name].append(step)
        
        # Формируем чистую историю
        for step_name in self.sgr_order:
            if step_name in grouped_steps:
                steps_of_type = grouped_steps[step_name]
                
                if step_name == "web_search" and len(steps_of_type) > 1:
                    # Для множественных поисков показываем сводку
                    total_time = sum(s.duration for s in steps_of_type)
                    clean_history.append({
                        "name": f"{step_name} (x{len(steps_of_type)})",
                        "duration": total_time,
                        "result": f"Completed {len(steps_of_type)} searches"
                    })
                else:
                    # Для остальных этапов берем последний
                    last_step = steps_of_type[-1]
                    clean_history.append({
                        "name": step_name,
                        "duration": last_step.duration,
                        "result": last_step.result
                    })
        
        return clean_history

# Пример использования
def demo_step_tracker():
    """Демонстрация работы трекера этапов"""
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    
    console = Console()
    tracker = SGRStepTracker()
    
    # Симулируем SGR процесс
    console.print(Panel("🎯 SGR Step Tracker Demo", border_style="cyan"))
    
    # Этап 1: Планирование
    tracker.start_step("generate_plan", "Creating research plan")
    time.sleep(0.5)
    tracker.complete_current_step({"goal": "Find BMW X6 prices", "steps": 3})
    
    # Этап 2: Первый поиск
    tracker.start_step("web_search", "First search")
    time.sleep(0.3)
    tracker.complete_current_step({"query": "BMW X6 prices", "sources": 5})
    
    # Этап 3: Второй поиск
    tracker.start_step("web_search", "Second search")
    time.sleep(0.4)
    tracker.complete_current_step({"query": "BMW X6 dealers", "sources": 3})
    
    # Этап 4: Создание отчета
    tracker.start_step("create_report", "Final report")
    time.sleep(0.2)
    tracker.complete_current_step({"title": "BMW X6 Price Analysis", "words": 500})
    
    # Показываем результаты
    summary = tracker.get_step_summary()
    history = tracker.get_clean_history()
    
    # Таблица сводки
    summary_table = Table(title="📊 Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")
    
    summary_table.add_row("Total Steps", str(summary["total_steps"]))
    summary_table.add_row("Total Time", f"{summary['total_time']:.1f}s")
    summary_table.add_row("Searches", str(summary["step_counts"].get("web_search", 0)))
    
    console.print(summary_table)
    
    # Таблица истории
    history_table = Table(title="📚 Clean History")
    history_table.add_column("Step", style="cyan")
    history_table.add_column("Duration", style="yellow")
    history_table.add_column("Result", style="green")
    
    for step in history:
        history_table.add_row(
            step["name"],
            f"{step['duration']:.1f}s",
            str(step["result"])[:50] + "..." if len(str(step["result"])) > 50 else str(step["result"])
        )
    
    console.print(history_table)

if __name__ == "__main__":
    demo_step_tracker()
