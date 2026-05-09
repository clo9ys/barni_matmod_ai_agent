import uuid
from fastapi import APIRouter, HTTPException
from src.core.state import ResearchState, ResearchDefinition, DataSource
from src.tools.search import load_registry, find_datasets  # те функции, что мы обсуждали

router = APIRouter(tags=["research"])

# хранилище сессий в памяти
sessions: dict[str, ResearchState] = {}


@router.post("/start", response_model=ResearchState)
async def start_research(query: str):
    # инициация сессии и первый проход по шагу 2
    session_id = str(uuid.uuid4())
    state = ResearchState(session_id=session_id, query=query)

    # имитация вызова мл-логики для шага 2
    state.add_trace("инициализация исследования")
    state.definition = ResearchDefinition(
        geography="определяется...",
        time_period="2015-2024",
        disciplinary_focus="экономика",
        research_questions=["динамика показателя", "сравнение по странам"]
    )
    state.add_trace("шаг 2: параметры определены (mock)")

    sessions[session_id] = state
    return state


@router.post("/next/{session_id}", response_model=ResearchState)
async def proceed(session_id: str, feedback: str | None = None):
    # основной движок пайплайна
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="сессия не найдена")

    state = sessions[session_id]

    # если пользователь прислал правки, остаемся на текущем шаге
    if feedback:
        state.add_trace(f"получены правки на шаге {state.current_step}: {feedback}")
        # тут в будущем будет вызов перегенерации через llm
        return state

    # если правок нет, двигаемся к следующему логическому блоку
    state.current_step += 1

    # логика шага 5: поиск данных
    if state.current_step == 5:
        state.add_trace("запуск поиска источников в реестре")
        registry = load_registry()
        # ищем по дисциплинарному фокусу или по самому запросу
        found = find_datasets(state.query, registry)

        if not found:
            state.add_trace("данные в реестре не найдены")
            state.errors.append("в базе данных нет подходящих наборов")
        else:
            from src.core.state import AssemblyPlan
            state.assembly_plan = AssemblyPlan(
                sources=found,
                plan_description="данные найдены, готовы к сборке"
            )
            state.add_trace(f"найдено источников: {len(found)}")

    state.add_trace(f"переход на шаг {state.current_step}")
    return state


@router.get("/status/{session_id}", response_model=ResearchState)
async def get_status(session_id: str):
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="сессия не найдена")
    return sessions[session_id]