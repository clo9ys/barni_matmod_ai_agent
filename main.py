import uuid
from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.table import Table
from src.core.state import (
    ResearchState,
    ResearchDefinition,
    ResearchDesign,
    AssemblyPlan,
    DataSource
)

console = Console()


def run_pipeline():
    # инициализация сессии и стартового запроса
    console.print(Panel.fit("ai-ассистент нцсэд: запуск исследовательского цикла", style="bold blue"))

    query = console.input("[bold green]запрос:[/bold green] ")
    if not query:
        query = "динамика ввп стран брикс за 2015-2024 годы"  # дефолтный запрос для теста

    state = ResearchState(
        session_id=str(uuid.uuid4()),
        query=query,
        generated_script=None,
        final_dataset_url=None,
    )

    # шаг 2: определение исследования (пока заглушка)
    with Status("[bold yellow]шаг 2: формализация запроса...", spinner="dots"):
        state.add_trace("анализ интента пользователя")
        state.definition = ResearchDefinition(
            geography="страны брикс (бразилия, россия, индия, китай, юар)",
            time_period="2015-2024",
            disciplinary_focus="макроэкономика",
            research_questions=["как изменился суммарный ввп?", "кто лидер роста?"]
        )
        state.add_trace("параметры исследования определены")

    _render_artifact("определение исследования", state.definition.dict())

    # шаг 3: дизайн исследования
    with Status("[bold yellow]шаг 3: проектирование гипотез...", spinner="dots"):
        state.add_trace("формулировка гипотез и выбор индикаторов")
        state.design = ResearchDesign(
            hypotheses=["ввп китая растет быстрее остальных стран блока"],
            indicators=["gdp (current usd)", "gdp growth (annual %)"],
            grouping_methods="агрегация по годам и странам"
        )

    _render_artifact("дизайн исследования", state.design.dict())

    # шаг 5: поиск источников (имитация рага)
    with Status("[bold yellow]шаг 5: поиск данных в реестре...", spinner="dots"):
        state.add_trace("запрос к векторной базе faiss")
        mock_source = DataSource(
            id="ds_001",
            title="world bank macroeconomics data",
            source_url="https://repository.nsedc.ru/wb_data",
            relevance_score=0.98,
            description="основные макропоказатели по странам мира"
        )
        state.assembly_plan = AssemblyPlan(
            sources=[mock_source],
            plan_description="извлечение ввп через api мирового банка"
        )
        state.add_trace(f"найден подходящий источник: {mock_source.title}")

    _render_artifact("план сборки и источники", state.assembly_plan.dict())

    # финальный вывод следа ассистента
    _render_trace(state.trace)


def _render_artifact(title: str, data: dict):
    # вспомогательная функция для отрисовки блоков данных
    table = Table(show_header=False, box=None)
    for key, value in data.items():
        table.add_row(f"[bold cyan]{key}:[/bold cyan]", str(value))

    console.print(Panel(table, title=f"[bold white]{title}[/bold white]", border_style="green"))


def _render_trace(trace: list):
    # отрисовка логов (след ассистента)
    console.print("\n[bold]след ассистента:[/bold]")
    for i, message in enumerate(trace, 1):
        console.print(f"  [dim]{i}. {message}[/dim]")


if __name__ == "__main__":
    try:
        run_pipeline()
    except KeyboardInterrupt:
        console.print("\n[red]работа прервана пользователем[/red]")