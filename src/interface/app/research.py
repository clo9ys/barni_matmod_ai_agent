import asyncio
import json
import uuid
import os
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from sse_starlette.sse import EventSourceResponse

from src.core.database import ResearchTable, User, get_session, engine
from src.interface.app.auth import get_current_user
from src.ml.model import complete_json
from src.ml.prompts import (
    build_extract_params_messages,
    build_research_design_messages,
    build_assembly_plan_messages
)
from src.ml.rag import search_datasets
from src.ml.reranker import rerank_datasets
from src.ml.codegen import generate_analysis_code
from src.tools.validator import validate_assembly_plan

router = APIRouter(tags=["research"])

# Хранилище очередей
event_queues: Dict[str, asyncio.Queue] = {}


async def push_event(task_id: str, data: dict):
    if task_id in event_queues:
        await event_queues[task_id].put(data)


async def run_agent_worker(task_id: str, query: str, user_id: int):
    print(f"\n🚀 [WORKER START] Task ID: {task_id}")
    archive_root = os.getenv("ARCHIVE_ROOT", "data/archive")

    # Небольшая пауза для стабильности стрима
    await asyncio.sleep(1)

    with Session(engine) as db:
        db_state = db.exec(select(ResearchTable).where(ResearchTable.session_id == task_id)).first()
        if not db_state: return

        try:
            # Шаг 2
            await push_event(task_id, {"type": "log", "message": "🧠 Анализирую запрос..."})
            params = complete_json(build_extract_params_messages(query))
            db_state.definition = params
            db_state.trace = db_state.trace + ["Параметры извлечены"]
            db.add(db_state)
            db.commit()
            db.refresh(db_state)

            await push_event(task_id, {
                "type": "step_update", "step": 1,
                "artifact": {
                    "geography": ", ".join(params.get("geography", [])),
                    "timeframe": str(params.get("time_period", {}).get("start", "...")),
                    "perspective": params.get("subject_area", "Экономика"),
                    "questions": params.get("clarifying_questions", [])
                }
            })

            # Шаг 3
            await push_event(task_id, {"type": "log", "message": "📋 Проектирую исследование..."})
            design = complete_json(build_research_design_messages(query, params))
            db_state.design = design
            db_state.trace = db_state.trace + ["Дизайн сформирован"]
            db.add(db_state)
            db.commit()
            db.refresh(db_state)

            await push_event(task_id, {
                "type": "step_update", "step": 2,
                "artifact": {
                    "hypotheses": [
                        {"id": i, "title": h['hypothesis'], "metrics": h['required_indicators'], "selected": True}
                        for i, h in enumerate(design.get('hypotheses', []))
                    ]
                }
            })

            # Шаг 5
            await push_event(task_id, {"type": "log", "message": "🔍 Поиск в реестре..."})
            candidates = search_datasets(query, top_k=10)
            top_datasets = rerank_datasets(query, candidates, top_k=3)
            assembly_plan = {}

            if top_datasets:
                best_ds = top_datasets[0]
                await push_event(task_id, {
                    "type": "step_update", "step": 4,
                    "artifact": {
                        "title": best_ds['title'],
                        "tags": best_ds.get('tags', []),
                        "description": best_ds['description'],
                        "url": best_ds.get('source_url', "#")
                    }
                })

                # План и Валидация
                plan_msg = build_assembly_plan_messages(query, params, top_datasets, design)
                assembly_plan = complete_json(plan_msg)

                # Фикс путей
                for src in assembly_plan.get("primary_sources", []):
                    if not src.get("file_path"):
                        match = next((d for d in top_datasets if d['id'] == src.get('dataset_id')), None)
                        if match: src["file_path"] = match.get("file_path")

                db_state.assembly_plan = assembly_plan
                db_state.trace = db_state.trace + ["План сборки готов"]
                db.add(db_state)
                db.commit()
                db.refresh(db_state)

                val_errors = validate_assembly_plan(assembly_plan, archive_root=archive_root)
                if val_errors:
                    await push_event(task_id, {"type": "log", "message": f"⚠️ Валидация: {val_errors[0]}"})

            # Шаг 6
            await push_event(task_id, {"type": "log", "message": "💻 Генерация кода..."})
            code = generate_analysis_code(query, design, top_datasets, archive_root, assembly_plan)
            db_state.generated_script = code
            db_state.current_step = 7
            db.add(db_state);
            db.commit()

            await push_event(task_id, {"type": "done"})
            print(f"🏁 [WORKER DONE] {task_id}")

        except Exception as e:
            print(f"❌ [WORKER ERROR]: {e}")
            await push_event(task_id, {"type": "error", "message": str(e)})


@router.post("/chat")
async def init_chat(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    body = await request.json()
    query = body.get("query")
    task_id = str(uuid.uuid4())
    event_queues[task_id] = asyncio.Queue()

    new_research = ResearchTable(session_id=task_id, query=query, user_id=user.id, trace=["Запуск задачи"])
    db.add(new_research)
    db.commit()

    asyncio.create_task(run_agent_worker(task_id, query, user.id))
    return {"task_id": task_id}


@router.get("/stream/{task_id}")
async def stream_task(request: Request, task_id: str, db: Session = Depends(get_session)):
    async def event_generator():
        # Если очереди нет в памяти, проверяем базу
        if task_id not in event_queues:
            db_state = db.exec(select(ResearchTable).where(ResearchTable.session_id == task_id)).first()
            if db_state and db_state.current_step >= 7:
                yield {"data": json.dumps({"type": "done"})}
                return
            else:
                yield {"data": json.dumps({"type": "error", "message": "Task not found or lost due to server reload"})}
                return

        queue = event_queues[task_id]
        try:
            while True:
                if await request.is_disconnected(): break
                event_data = await queue.get()
                yield {"data": json.dumps(event_data, ensure_ascii=False)}
                if event_data.get("type") in ["done", "error"]: break
        finally:
            # Не удаляем сразу, даем шанс React Strict Mode
            await asyncio.sleep(5)
            if task_id in event_queues: del event_queues[task_id]

    return EventSourceResponse(event_generator())


@router.get("/research/{session_id}")
async def get_research_detail(session_id: str, db: Session = Depends(get_session),
                              user: User = Depends(get_current_user)):
    state = db.exec(select(ResearchTable).where(ResearchTable.session_id == session_id)).first()
    if not state or state.user_id != user.id:
        raise HTTPException(status_code=404)
    return state


@router.get("/history")
async def get_history(user: User = Depends(get_current_user)):
    return user.researches