import asyncio
import json
import uuid
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
event_queues: Dict[str, asyncio.Queue] = {}

def run_agent_worker(task_id: str, query: str, user_id: int):
    loop = asyncio.get_event_loop()

    def sync_push(data: dict):
        if task_id in event_queues:
            asyncio.run_coroutine_threadsafe(event_queues[task_id].put(data), loop)

    with Session(engine) as db:
        try:
            sync_push({"type": "log", "message": "🤖 Запуск агента. Анализирую запрос..."})

            params_messages = build_extract_params_messages(query)
            params = complete_json(params_messages)

            db_state = db.exec(select(ResearchTable).where(ResearchTable.session_id == task_id)).first()
            db_state.definition = params
            db_state.trace.append("Шаг 2 выполнен: параметры извлечены")
            db.add(db_state)
            db.commit()

            sync_push({
                "type": "step_update",
                "step": 1,
                "artifact": {
                    "geography": ", ".join(params.get("geography", [])),
                    "timeframe": f"{params.get('time_period', {}).get('start', '...')}",
                    "perspective": params.get("subject_area", "Экономика"),
                    "questions": params.get("clarifying_questions", [])
                }
            })

            sync_push({"type": "log", "message": "📝 Формирую гипотезы и дизайн исследования..."})
            design_messages = build_research_design_messages(query, params)
            design = complete_json(design_messages)

            db_state.design = design
            db_state.current_step = 3
            db.add(db_state)
            db.commit()

            sync_push({
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

            sync_push({"type": "log", "message": "🔍 Ищу подходящие датасеты в реестре НЦСЭД..."})
            search_query = f"{query} {params.get('subject_area', '')}"
            found_datasets = search_datasets(search_query, top_k=3)

            if found_datasets:
                best_ds = found_datasets[0]
                db_state.assembly_plan = {"sources": found_datasets, "plan": "Интеграция через Python/Pandas"}
                db_state.current_step = 5
                db.add(db_state)
                db.commit()

                sync_push({
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
                sync_push({"type": "log", "message": "⚠️ Данные в реестре не найдены."})

            sync_push({"type": "log", "message": "⚙️ Генерация кода сборки..."})
            db_state.generated_script = "import pandas as pd\nprint('Сборка завершена')"
            db_state.current_step = 7
            db.add(db_state)
            db.commit()

            sync_push({"type": "done"})

        except Exception as e:
            sync_push({"type": "error", "message": f"Ошибка агента: {str(e)}"})
            if db_state:
                db_state.errors.append(str(e))
                db.add(db_state)
                db.commit()

@router.post("/chat")
async def init_chat(
        request: Request,
        background_tasks: BackgroundTasks,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_session)
):
    body = await request.json()
    query = body.get("query")
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    task_id = str(uuid.uuid4())
    event_queues[task_id] = asyncio.Queue()

    new_research = ResearchTable(
        session_id=task_id,
        query=query,
        user_id=user.id,
        trace=["Запуск задачи через API"]
    )
    db.add(new_research)
    db.commit()

    background_tasks.add_task(run_agent_worker, task_id, query, user.id)
    return {"task_id": task_id}

@router.get("/stream/{task_id}")
async def stream_task(request: Request, task_id: str):
    async def event_generator():
        if task_id not in event_queues:
            yield {"data": json.dumps({"type": "error", "message": "Task not found"})}
            return

        queue = event_queues[task_id]
        try:
            while True:
                if await request.is_disconnected():
                    break
                event_data = await queue.get()
                yield {"data": json.dumps(event_data, ensure_ascii=False)}
                if event_data.get("type") in ["done", "error"]:
                    break
        except Exception as e:
            yield {"data": json.dumps({"type": "error", "message": str(e)})}
        finally:
            if task_id in event_queues:
                del event_queues[task_id]

    return EventSourceResponse(event_generator())

@router.get("/history")
async def get_history(user: User = Depends(get_current_user)):
    return user.researches

@router.get("/research/{session_id}")
async def get_research_detail(
        session_id: str,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_session)
):
    statement = select(ResearchTable).where(
        ResearchTable.session_id == session_id,
        ResearchTable.user_id == user.id
    )
    research = db.exec(statement).first()
    if not research:
        raise HTTPException(status_code=404, detail="Исследование не найдено")
    return research