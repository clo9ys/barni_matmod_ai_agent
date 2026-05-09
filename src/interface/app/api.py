from fastapi import HTTPException, APIRouter
from src.core.state import ResearchState, ResearchDefinition

router = APIRouter()

# временное хранилище сессий
sessions = {}


@router.post("/start")
async def start_research(query: str):
    # инициация нового исследования
    import uuid
    session_id = str(uuid.uuid4())
    state = ResearchState(session_id=session_id, query=query)

    # тут в будущем будет вызов реального шага 2
    # пока отдаем заглушку
    state.definition = ResearchDefinition(
        geography="рф",
        time_period="2023",
        disciplinary_focus="экономика",
        research_questions=["тестовый вопрос"]
    )
    state.add_trace("сессия создана, параметры определены (mock)")

    sessions[session_id] = state
    return state


@router.get("/status/{session_id}")
async def get_status(session_id: str):
    # получение текущего состояния для фронта
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="сессия не найдена")
    return sessions[session_id]