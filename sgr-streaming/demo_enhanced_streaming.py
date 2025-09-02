#!/usr/bin/env python3
"""
Demo Enhanced Streaming for SGR
Демонстрация улучшенного стриминга для SGR системы
"""

import time
import json
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.layout import Layout

from enhanced_streaming import enhanced_streaming_display, EnhancedSchemaParser
from sgr_visualizer import SGRLiveMonitor, demo_sgr_visualization

def demo_json_streaming_parsing():
    """Демонстрация парсинга JSON в реальном времени"""
    console = Console()
    
    console.print(Panel(
        "🚀 [bold cyan]Enhanced JSON Streaming Demo[/bold cyan]\n"
        "Показываем как красиво парсится JSON схема в реальном времени",
        title="Demo",
        border_style="cyan"
    ))
    
    # Пример JSON схемы для стриминга
    sample_next_step_json = '''{
    "reasoning_steps": [
        "Пользователь запросил исследование цен на BMW X6",
        "Нужно создать план исследования",
        "Определяем стратегию поиска информации"
    ],
    "current_situation": "Получен запрос на исследование автомобильного рынка",
    "plan_status": "Не создан - требуется формирование плана",
    "searches_done": 0,
    "enough_data": false,
    "remaining_steps": [
        "Создать план исследования",
        "Провести веб-поиск",
        "Создать отчет"
    ],
    "task_completed": false,
    "function": {
        "tool": "generate_plan",
        "reasoning": "Необходимо создать структурированный план для эффективного исследования рынка BMW X6",
        "research_goal": "Исследовать актуальные цены на BMW X6 2025 года в России",
        "planned_steps": [
            "Поиск информации на официальных сайтах BMW",
            "Анализ цен у авторизованных дилеров",
            "Сравнение с данными автомобильных порталов",
            "Составление сводного отчета с ценовыми диапазонами"
        ],
        "search_strategies": [
            "Официальные источники BMW России",
            "Авторизованные дилерские центры",
            "Автомобильные порталы и агрегаторы цен"
        ]
    }
}'''
    
    # Создаем парсер
    parser = EnhancedSchemaParser(console)
    
    # Симулируем стриминг по частям
    layout = Layout()
    
    with Live(layout, console=console, refresh_per_second=8) as live:
        accumulated = ""
        
        # Стримим JSON по кускам
        chunk_size = 30
        for i in range(0, len(sample_next_step_json), chunk_size):
            chunk = sample_next_step_json[i:i+chunk_size]
            accumulated += chunk
            
            # Обновляем отображение
            display = parser.update_from_stream_chunk(chunk)
            layout.update(display)
            
            time.sleep(0.1)  # Симуляция задержки сети
        
        # Показываем финальный результат
        time.sleep(1.5)
    
    console.print("\n✅ [bold green]JSON Streaming Demo Complete![/bold green]")

def demo_schema_specific_displays():
    """Демонстрация специализированных отображений для разных схем"""
    console = Console()
    
    console.print(Panel(
        "🎨 [bold magenta]Schema-Specific Displays Demo[/bold magenta]\n"
        "Показываем специализированные отображения для разных типов схем",
        title="Demo",
        border_style="magenta"
    ))
    
    # Демонстрируем разные типы схем
    schemas = {
        "clarification": {
            "tool": "clarification",
            "reasoning": "Запрос пользователя содержит неопределенности",
            "unclear_terms": ["BMW X6", "актуальные цены", "2025 год"],
            "assumptions": [
                "Пользователя интересуют цены в России",
                "Нужны цены на новые автомобили"
            ],
            "questions": [
                "Интересуют ли вас цены на новые или подержанные BMW X6?",
                "Нужны ли данные по конкретным комплектациям?",
                "Рассматриваете ли вы конкретные регионы России?"
            ]
        },
        "web_search": {
            "tool": "web_search",
            "reasoning": "Необходимо найти актуальную информацию о ценах BMW X6",
            "query": "BMW X6 2025 цены России официальные дилеры",
            "max_results": 10,
            "scrape_content": True
        },
        "create_report": {
            "tool": "create_report",
            "reasoning": "Собрано достаточно данных для создания отчета",
            "title": "Анализ цен на BMW X6 2025 года в России",
            "confidence": "high",
            "content": "# Исполнительное резюме\n\nИсследование показало, что цены на BMW X6 2025 года в России варьируются от 8.5 до 12.5 млн рублей..."
        }
    }
    
    for schema_name, schema_data in schemas.items():
        console.print(f"\n📋 [bold cyan]Schema: {schema_name}[/bold cyan]")
        
        parser = EnhancedSchemaParser(console)
        json_str = json.dumps(schema_data, ensure_ascii=False, indent=2)
        
        # Симулируем быстрый стриминг
        display = parser.update_from_stream_chunk(json_str)
        console.print(display)
        time.sleep(1)

def demo_full_sgr_process():
    """Демонстрация полного SGR процесса с мониторингом"""
    console = Console()
    
    console.print(Panel(
        "🔄 [bold green]Full SGR Process Demo[/bold green]\n"
        "Показываем полный мониторинг SGR процесса с визуализацией",
        title="Demo",
        border_style="green"
    ))
    
    # Запускаем демо из sgr_visualizer
    demo_sgr_visualization()

def main():
    """Главная демонстрация всех возможностей"""
    console = Console()
    
    console.print(Panel(
        "[bold cyan]🚀 Enhanced Streaming Demo Suite 🚀[/bold cyan]\n\n"
        "Демонстрация улучшенного стриминга для SGR системы:\n"
        "• JSON парсинг в реальном времени\n"
        "• Специализированные отображения схем\n"
        "• Полный мониторинг SGR процесса\n"
        "• Анимации и интерактивные элементы",
        title="🎯 Enhanced SGR Streaming",
        border_style="cyan"
    ))
    
    demos = [
        ("1", "JSON Streaming Parser", demo_json_streaming_parsing),
        ("2", "Schema-Specific Displays", demo_schema_specific_displays),
        ("3", "Full SGR Process Monitor", demo_full_sgr_process),
        ("4", "All Demos", None)
    ]
    
    for num, name, func in demos:
        console.print(f"  {num}. [cyan]{name}[/cyan]")
    
    while True:
        try:
            choice = input("\n🔢 Select demo (1-4) or 'q' to quit: ").strip()
            
            if choice.lower() == 'q':
                console.print("👋 [bold yellow]Goodbye![/bold yellow]")
                break
            
            if choice == "1":
                demo_json_streaming_parsing()
            elif choice == "2":
                demo_schema_specific_displays()
            elif choice == "3":
                demo_full_sgr_process()
            elif choice == "4":
                console.print("\n🎬 [bold cyan]Running all demos...[/bold cyan]")
                demo_json_streaming_parsing()
                console.print("\n" + "="*60)
                demo_schema_specific_displays()
                console.print("\n" + "="*60)
                demo_full_sgr_process()
            else:
                console.print("❌ [red]Invalid choice. Please select 1-4 or 'q'[/red]")
                
        except KeyboardInterrupt:
            console.print("\n👋 [bold yellow]Demo interrupted. Goodbye![/bold yellow]")
            break
        except Exception as e:
            console.print(f"❌ [red]Error: {e}[/red]")

if __name__ == "__main__":
    main()
