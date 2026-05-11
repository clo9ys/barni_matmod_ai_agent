import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlmodel import Session, select
from sse_starlette.sse import EventSourceResponse
from src.core.database import ResearchTable, User, get_session, engine
from src.interface.app.auth import get_current_user
from src.ml.model import complete_json
from src.ml.prompts import build_extract_params_messages, build_research_design_messages
from src.ml.rag import search_datasets

router = APIRouter(tags=["research"])

# Глобальное хранилище очередей для стриминга
# task_id -> asyncio.Queue
event_queues: Dict[str, asyncio.Queue] = {}


async def push_event(task_id: str, data: dict):
    """Отправка события в очередь фронтенда"""
    if task_id in event_queues:
        await event_queues[task_id].put(data)


async def run_agent_worker(task_id: str, query: str, user_id: int):
    """
    Фоновый воркер, который проходит по всем шагам ТЗ
    и пушит события фронтенду через SSE.
    """
    # Создаем свою сессию БД для фонового потока
    with Session(engine) as db:
        db_state = None
        try:
            # 1. Инициализация и Шаг 2 (Определение)
            await push_event(task_id, {"type": "log", "message": "🤖 Запуск агента. Анализирую запрос..."})

            params_messages = build_extract_params_messages(query)
            params = await asyncio.to_thread(complete_json, params_messages)

            # Сохраняем в БД
            db_state = db.exec(select(ResearchTable).where(ResearchTable.session_id == task_id)).first()
            if db_state is None:
                raise RuntimeError(f"ResearchTable record not found for task_id={task_id}")
            db_state.definition = params
            db_state.trace = db_state.trace + ["Шаг 2 выполнен: параметры извлечены"]
            db.add(db_state)
            db.commit()

            # Пушим на фронт (ResearchDefinitionCard)
            await push_event(task_id, {
                "type": "step_update",
                "step": 1,
                "artifact": {
                    "geography": ", ".join(params.get("geography", [])),
                    "timeframe": f"{params.get('time_period', {}).get('start', '...')}",
                    "perspective": params.get("subject_area", "Экономика"),
                    "questions": params.get("clarifying_questions", [])
                }
            })

            # 2. Шаг 3 (Дизайн исследования / Гипотезы)
            await push_event(task_id, {"type": "log", "message": "📝 Формирую гипотезы и дизайн исследования..."})

            search_query = f"{query} {params.get('subject_area', '')}"
            found_datasets = await asyncio.to_thread(search_datasets, search_query, 3)

            design_messages = build_research_design_messages(query, params, found_datasets)
            design = await asyncio.to_thread(complete_json, design_messages)

            db_state.design = design
            db_state.current_step = 3
            db.add(db_state)
            db.commit()

            # Пушим на фронт (HypothesisCard)
            await push_event(task_id, {
                "type": "step_update",
                "step": 2,
                "artifact": {
                    "hypotheses": [
                        {
                            "id": i,
                            "title": h.get('hypothesis'),
                            "metrics": h.get('required_indicators', []),
                            "selected": True
                        } for i, h in enumerate(design.get('hypotheses', []))
                    ]
                }
            })

            # 3. Шаг 5 (Поиск в реестре через RAG/FAISS)
            await push_event(task_id, {"type": "log", "message": "🔍 Ищу подходящие датасеты в реестре НЦСЭД..."})

            if found_datasets:
                best_ds = found_datasets[0]
                db_state.assembly_plan = {"sources": found_datasets, "plan": "Интеграция через Python/Pandas"}
                db_state.current_step = 5
                db.add(db_state)
                db.commit()

                # Пушим на фронт (SourceCard)
                await push_event(task_id, {
                    "type": "step_update",
                    "step": 4,
                    "artifact": {
                        "title": best_ds.get('title'),
                        "tags": best_ds.get('tags', []),
                        "description": best_ds.get('description'),
                        "url": best_ds.get('source_url', "#")
                    }
                })
            else:
                await push_event(task_id, {"type": "log", "message": "⚠️ Данные в реестре не найдены."})

            # 4. Шаг 6 и 7 (Скрипт и Сборка)
            await push_event(task_id, {"type": "log", "message": "⚙️ Генерация кода сборки..."})
            db_state.generated_script = "import pandas as pd\nprint('Сборка завершена')"
            db_state.current_step = 7
            db.add(db_state)
            db.commit()

            # Финальное событие
            await push_event(task_id, {"type": "done"})

        except Exception as e:
            await push_event(task_id, {"type": "error", "message": f"Ошибка агента: {str(e)}"})
            if db_state is not None:
                db_state.errors = db_state.errors + [str(e)]
                db.add(db_state)
                db.commit()


@router.post("/chat")
async def init_chat(
        request: Request,
        background_tasks: BackgroundTasks,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_session)
):
    """Эндпоинт 1: Принимает запрос и запускает воркер"""
    body = await request.json()
    query = body.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    task_id = str(uuid.uuid4())

    # Инициализируем очередь для стриминга
    event_queues[task_id] = asyncio.Queue()

    # Создаем запись в истории
    new_research = ResearchTable(
        session_id=task_id,
        query=query,
        user_id=user.id,
        trace=["Запуск задачи через API"]
    )
    db.add(new_research)
    db.commit()

    # Запускаем тяжелую логику в фоне
    background_tasks.add_task(run_agent_worker, task_id, query, user.id)

    return {"task_id": task_id}


@router.get("/stream/{task_id}")
async def stream_task(request: Request, task_id: str):
    """Эндпоинт 2: Стриминг событий через SSE"""

    async def event_generator():
        if task_id not in event_queues:
            yield {"data": json.dumps({"type": "error", "message": "Task not found"})}
            return

        queue = event_queues[task_id]

        try:
            while True:
                # Если клиент закрыл вкладку - выходим
                if await request.is_disconnected():
                    break

                # Получаем событие из очереди воркера
                event_data = await queue.get()

                # Отправляем в формате SSE
                yield {"data": json.dumps(event_data, ensure_ascii=False)}

                # Если это было финальное событие - закрываем стрим
                if event_data.get("type") in ["done", "error"]:
                    break
        except Exception as e:
            yield {"data": json.dumps({"type": "error", "message": str(e)})}
        finally:
            # Очистка очереди
            if task_id in event_queues:
                del event_queues[task_id]

    return EventSourceResponse(event_generator())


@router.get("/history")
async def get_history(user: User = Depends(get_current_user)):
    """История запросов пользователя"""
    return user.researches