import os
import asyncio
import json
import uuid
from pathlib import Path
from typing import Dict, Tuple
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlmodel import Session, select
from sse_starlette.sse import EventSourceResponse
from src.core.database import ResearchTable, User, get_session, engine
from src.interface.app.auth import get_current_user

# Импорты ML-пайплайна
from src.ml.model import complete_json, is_llm_configured
from src.ml.prompts import build_extract_params_messages, build_research_design_messages, build_assembly_plan_messages
from src.ml.rag import FAISS_INDEX_PATH, METADATA_PATH, search_datasets
from src.ml.reranker import rerank_datasets
from src.tools.readers import read_fedstatru_coverage
from src.tools.validator import validate_assembly_plan
from src.ml.codegen import generate_analysis_code
from src.core.pipeline import _build_english_query, _merge_candidates, NO_DATA_RERANK_THRESHOLD

router = APIRouter(tags=["research"])
event_queues: Dict[str, Tuple[asyncio.Queue, asyncio.AbstractEventLoop]] = {}

def run_agent_worker(task_id: str, query: str, user_id: int, loop: asyncio.AbstractEventLoop):
    def sync_push(data: dict):
        if task_id in event_queues:
            queue, main_loop = event_queues[task_id]
            asyncio.run_coroutine_threadsafe(queue.put(data), main_loop)

    with Session(engine) as db:
        db_state = db.exec(select(ResearchTable).where(ResearchTable.session_id == task_id)).first()

        try:
            if not is_llm_configured():
                raise RuntimeError("LLM не настроена. Укажите AI_API_KEY и AI_MODEL в .env")

            archive_root = os.getenv("ARCHIVE_ROOT", "")

            # ШАГ 1: ПАРАМЕТРЫ
            sync_push({"type": "log", "message": "🤖 Извлекаю параметры исследования..."})
            extracted_params = complete_json(build_extract_params_messages(query))
            if db_state:
                db_state.definition = extracted_params
                db.add(db_state)
                db.commit()

            if extracted_params.get("query_type") == "no_data":
                sync_push({"type": "error", "message": "Тема вне компетенции агента."})
                return

            sync_push({
                "type": "step_update", "step": 1,
                "artifact": {
                    "geography": ", ".join(extracted_params.get("geography", [])),
                    "timeframe": f"{extracted_params.get('time_period', {}).get('start', '...')}",
                    "perspective": extracted_params.get("subject_area", "Экономика"),
                    "questions": extracted_params.get("clarifying_questions", [])
                }
            })

            # ШАГ 2: ПОИСК (ИСТОЧНИКИ) - Теперь это Шаг 2
            sync_push({"type": "log", "message": "🔍 Поиск в реестре НЦСЭД..."})
            candidates = search_datasets(query, top_k=20, index_path=FAISS_INDEX_PATH, metadata_path=METADATA_PATH)
            top_datasets = rerank_datasets(query, candidates, top_k=5)

            if not top_datasets or max((d.get("rerank_score", 0.0) for d in top_datasets), default=0.0) < NO_DATA_RERANK_THRESHOLD:
                sync_push({"type": "error", "message": "Релевантные данные не найдены."})
                return

            sync_push({
                "type": "step_update", "step": 2,
                "artifact": {
                    "title": top_datasets[0].get('title'),
                    "tags": top_datasets[0].get('tags', []),
                    "description": top_datasets[0].get('description'),
                    "url": top_datasets[0].get('source_url', "#")
                }
            })

            # ШАГ 3: ДИЗАЙН (ГИПОТЕЗЫ) - Теперь это Шаг 3
            sync_push({"type": "log", "message": "📝 Генерация гипотез..."})
            research_design = complete_json(build_research_design_messages(query, extracted_params, top_datasets))

            if db_state:
                db_state.design = research_design
                db.add(db_state)
                db.commit()

            sync_push({
                "type": "step_update", "step": 3,
                "artifact": {
                    "hypotheses": [
                        {"id": i, "title": h.get('hypothesis'), "metrics": h.get('required_indicators', []), "selected": True}
                        for i, h in enumerate(research_design.get('hypotheses', []))
                    ]
                }
            })

            # ШАГ 4: ПЛАН И ВАЛИДАЦИЯ
            sync_push({"type": "log", "message": "⚙️ Составление плана сборки..."})
            assembly_plan = complete_json(build_assembly_plan_messages(query, extracted_params, top_datasets, research_design))

            if db_state:
                db_state.assembly_plan = assembly_plan
                db.add(db_state)
                db.commit()

            if archive_root:
                errors = validate_assembly_plan(assembly_plan, archive_root=archive_root)
                if errors:
                    sync_push({"type": "error", "message": f"Ошибка валидации: {errors}"})
                    return

            # Отправляем заглушку для шага 4 (чтобы UI знал, что план готов)
            sync_push({"type": "step_update", "step": 4, "artifact": {"plan": "Валидация пройдена"}})

            # ШАГ 5: CODEGEN
            sync_push({"type": "log", "message": "💻 Написание кода обработки..."})
            code = generate_analysis_code(query, research_design, top_datasets, archive_root=archive_root, assembly_plan=assembly_plan)

            if db_state:
                db_state.generated_script = code
                db_state.current_step = 6
                db.add(db_state)
                db.commit()

            sync_push({"type": "step_update", "step": 5, "artifact": {"code": code}})
            sync_push({"type": "step_update", "step": 6, "artifact": {"message": "Скрипт готов к выполнению"}})
            sync_push({"type": "done"})

        except Exception as e:
            sync_push({"type": "error", "message": str(e)})
        finally:
            # Удаляем очередь ТОЛЬКО когда воркер полностью завершил работу
            if task_id in event_queues:
                del event_queues[task_id]

@router.post("/chat")
async def init_chat(request: Request, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    body = await request.json()
    query = body.get("query")
    task_id = str(uuid.uuid4())
    main_loop = asyncio.get_running_loop()

    event_queues[task_id] = (asyncio.Queue(), main_loop)

    new_research = ResearchTable(session_id=task_id, query=query, user_id=user.id, trace=["Запуск"])
    db.add(new_research)
    db.commit()

    background_tasks.add_task(run_agent_worker, task_id, query, user.id, main_loop)
    return {"task_id": task_id}

@router.get("/stream/{task_id}")
async def stream_task(request: Request, task_id: str):
    async def event_generator():
        if task_id not in event_queues:
            yield {"data": json.dumps({"type": "error", "message": "Task not found"})}
            return
        queue, _ = event_queues[task_id]
        try:
            while True:
                if await request.is_disconnected(): break # Выходим, но НЕ удаляем очередь
                event_data = await queue.get()
                yield {"data": json.dumps(event_data, ensure_ascii=False)}
                if event_data.get("type") in ["done", "error"]: break
        except Exception as e:
            pass # Игнорируем ошибки обрыва
    return EventSourceResponse(event_generator())

@router.get("/stream/{task_id}")
async def stream_task(request: Request, task_id: str):
    async def event_generator():
        if task_id not in event_queues:
            # Если мы здесь, значит сервер перезагрузился и память пуста
            yield {"data": json.dumps({"type": "error", "message": "Task not found (Server restarted)"})}
            return

        queue, _ = event_queues[task_id]
        try:
            while True:
                if await request.is_disconnected(): break
                event_data = await queue.get()
                yield {"data": json.dumps(event_data, ensure_ascii=False)}
                if event_data.get("type") in ["done", "error"]: break
        finally:
            if task_id in event_queues: del event_queues[task_id]

    return EventSourceResponse(event_generator())

@router.get("/history")
async def get_history(user: User = Depends(get_current_user)):
    return user.researches

@router.get("/research/{session_id}")
async def get_research_detail(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    res = db.exec(select(ResearchTable).where(ResearchTable.session_id == session_id, ResearchTable.user_id == user.id)).first()
    if not res: raise HTTPException(status_code=404)
    return res