import uuid
from rich.console import Console
from rich.panel import Panel
from rich.status import Status
from rich.prompt import Prompt, Confirm
from rich.table import Table
from src.core.state import (
    ResearchState,
    ResearchDefinition,
    ResearchDesign,
    AssemblyPlan,
    DataSource
)

console = Console()


def process_definition_step(state: ResearchState):
    # шаг 2: имитация логики уточнения запроса
    while True:
        with Status("[bold yellow]шаг 2: формализация запроса...", spinner="dots"):
            state.add_trace(f"анализ интента: {state.query}")

            # имитируем логику: если запрос слишком короткий, требуем уточнения
            if len(state.query.split()) < 3:
                state.add_trace("запрос слишком абстрактный")
                is_ambiguous = True
            else:
                is_ambiguous = False
                state.definition = ResearchDefinition(
                    geography="выбрано на основе запроса",
                    time_period="2020-2024",
                    disciplinary_focus="экономика",
                    research_questions=["основной индикатор", "динамика изменений"]
                )

        if is_ambiguous:
            console.print("[bold red]система:[/bold red] ваш запрос слишком общий. уточните географию или период.")
            state.query = Prompt.ask("[bold green]уточнение[/bold green]")
            state.add_trace(f"получено уточнение: {state.query}")
            continue  # идем на повторный круг анализа
        else:
            state.add_trace("параметры исследования формализованы")
            return True


def process_search_step(state: ResearchState):
    # шаг 5: поиск с ветвлением при отсутствии данных
    with Status("[bold yellow]шаг 5: поиск данных в реестре...", spinner="dots"):
        state.add_trace("поиск в faiss по метаданным")
        # имитация: если в запросе есть 'ошибка', данных не найдем
        if "ошибка" in state.query.lower():
            found = []
        else:
            found = [DataSource(
                id="ds_1", title="тестовый датасет", source_url="http://nsedc.ru",
                relevance_score=0.9, description="описание"
            )]

    if not found:
        state.add_trace("данные не найдены в реестре")
        console.print(
            Panel("[bold red]внимание:[/bold red] по вашему запросу нет данных в верифицированных источниках.",
                  border_style="red"))

        if Confirm.ask("хотите изменить параметры поиска?"):
            state.add_trace("пользователь решил изменить параметры")
            return "retry"  # ветвление: возврат назад
        else:
            state.add_trace("завершение работы из-за отсутствия данных")
            return "stop"

    state.assembly_plan = AssemblyPlan(sources=found, plan_description="план сборки готов")
    state.add_trace(f"найдено источников: {len(found)}")
    return "success"


def run_pipeline():
    console.print(Panel.fit("ai-ассистент нцсэд: гибридный пайплайн", style="bold blue"))

    query = Prompt.ask("[bold green]введите ваш запрос[/bold green]")
    state = ResearchState(session_id=str(uuid.uuid4()), query=query)

    # запуск этапов с логикой переходов
    if not process_definition_step(state):
        return

    _render_artifact("шаг 2: формализация", state.definition.dict())

    # шаг 3: дизайн (пропускаем для краткости, тут логика линейная)
    state.design = ResearchDesign(hypotheses=["тест"], indicators=["ввп"], grouping_methods="страны")
    _render_artifact("шаг 3: дизайн", state.design.dict())

    # шаг 5: поиск и выбор пути
    search_result = process_search_step(state)

    if search_result == "retry":
        # пример ветвления: возвращаемся на ввод запроса
        return run_pipeline()
    elif search_result == "stop":
        _render_trace(state.trace)
        return

    _render_artifact("шаг 5: поиск данных", state.assembly_plan.dict())

    # финальный вывод
    _render_trace(state.trace)


def _render_artifact(title: str, data: dict):
    table = Table(show_header=False, box=None)
    for key, value in data.items():
        table.add_row(f"[bold cyan]{key}:[/bold cyan]", str(value))
    console.print(Panel(table, title=f"[bold white]{title}[/bold white]", border_style="green"))


def _render_trace(trace: list):
    console.print("\n[bold]след ассистента:[/bold]")
    for i, message in enumerate(trace, 1):
        console.print(f"  [dim]{i}. {message}[/dim]")


if __name__ == "__main__":
    run_pipeline()