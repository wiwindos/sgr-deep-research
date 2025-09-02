#!/usr/bin/env python3
"""
Compact Streaming Example
Пример компактного стриминга без больших разрывов
"""

import time
import json
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.box import ROUNDED

def compact_streaming_demo():
    """Демонстрация компактного стриминга"""
    console = Console()
    
    console.print(Panel(
        "🎯 [bold cyan]Compact Streaming Demo[/bold cyan]\n"
        "Демонстрация стриминга без больших разрывов после завершения",
        title="Compact Demo",
        border_style="cyan",
        expand=False,
        width=60
    ))
    
    # Симулируем JSON стриминг
    sample_json = '''{
    "tool": "web_search",
    "reasoning": "Нужно найти информацию о ценах BMW X6",
    "query": "BMW X6 2025 цены России",
    "max_results": 10,
    "scrape_content": true
}'''
    
    layout = Layout()
    
    # Используем transient=False для сохранения контента после завершения
    with Live(layout, console=console, refresh_per_second=10, transient=False) as live:
        
        accumulated = ""
        
        # Стримим по кускам
        for i in range(0, len(sample_json), 15):
            chunk = sample_json[i:i+15]
            accumulated += chunk
            
            # Создаем компактную таблицу прогресса
            progress_table = Table(show_header=False, box=None, padding=(0, 1))
            progress_table.add_column("", style="cyan", width=12)
            progress_table.add_column("", style="white", width=25)
            
            progress = len(accumulated) / len(sample_json)
            bar_filled = int(progress * 20)
            bar = "█" * bar_filled + "░" * (20 - bar_filled)
            
            progress_table.add_row("📡 Streaming", f"{bar} {progress*100:.0f}%")
            progress_table.add_row("📝 Content", f"{len(accumulated)} chars")
            
            # Превью JSON
            preview = accumulated[-50:] if len(accumulated) > 50 else accumulated
            if not accumulated.strip().endswith('}'):
                preview += "..."
                
            progress_table.add_row("👀 Preview", preview[:30] + "..." if len(preview) > 30 else preview)
            
            # Компактная панель
            compact_panel = Panel(
                progress_table,
                title="🚀 JSON Streaming",
                border_style="yellow" if progress < 1.0 else "green",
                box=ROUNDED,
                expand=False,
                width=50
            )
            
            layout.update(compact_panel)
            time.sleep(0.08)
        
        # Финальное состояние
        final_table = Table(show_header=False, box=None, padding=(0, 1))
        final_table.add_column("", style="bold green", width=12)
        final_table.add_column("", style="white", width=25)
        
        final_table.add_row("✅ Complete", "JSON parsed successfully")
        final_table.add_row("📊 Schema", "web_search detected")
        final_table.add_row("⚡ Speed", f"{len(sample_json)/2:.0f} chars/sec")
        
        final_panel = Panel(
            final_table,
            title="🎯 Streaming Complete",
            border_style="green",
            box=ROUNDED,
            expand=False,
            width=50
        )
        
        layout.update(final_panel)
        time.sleep(1.0)  # Короткая пауза
    
    # После Live - показываем только краткую сводку
    console.print("\n✨ [bold green]Compact streaming demo finished![/bold green]")
    console.print("   No large gaps, clean output! 🎉")

def comparison_demo():
    """Сравнение обычного и компактного вывода"""
    console = Console()
    
    console.print(Panel(
        "📊 [bold magenta]Before vs After Comparison[/bold magenta]\n\n"
        "[red]BEFORE:[/red] Large gaps after streaming\n"
        "[green]AFTER:[/green] Compact, clean output\n\n"
        "Key improvements:\n"
        "• Fixed width panels (expand=False)\n"  
        "• Shorter display times (1s vs 3s)\n"
        "• Compact summary tables\n"
        "• No excessive whitespace",
        title="🔧 Improvements",
        border_style="magenta",
        expand=False,
        width=55
    ))

def main():
    """Главная функция демонстрации"""
    console = Console()
    
    console.print("[bold cyan]🎯 Compact Streaming Solutions[/bold cyan]\n")
    
    while True:
        choice = input("Choose demo: [1] Compact Streaming [2] Comparison [q] Quit: ").strip()
        
        if choice == '1':
            compact_streaming_demo()
        elif choice == '2':
            comparison_demo()
        elif choice.lower() == 'q':
            console.print("👋 [yellow]Goodbye![/yellow]")
            break
        else:
            console.print("❌ [red]Invalid choice[/red]")

if __name__ == "__main__":
    main()
