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

# Импорты реального ML-пайплайна
from src.ml.model import complete_json, is_llm_configured
from src.ml.prompts import (
    build_extract_params_messages,
    build_research_design_messages,
    build_assembly_plan_messages,
)
from src.ml.rag import (
    FAISS_INDEX_PATH,
    METADATA_PATH,
    search_datasets,
)
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

            # ---------------------------------------------------------
            # ШАГ 1: ИЗВЛЕЧЕНИЕ ПАРАМЕТРОВ
            # ---------------------------------------------------------
            sync_push({"type": "log", "message": "🤖 Извлекаю параметры исследования..."})
            params_messages = build_extract_params_messages(query)
            extracted_params = complete_json(params_messages)

            if db_state:
                db_state.definition = extracted_params
                db.add(db_state)
                db.commit()

            # Обработка Stop-логики из пайплайна
            if extracted_params.get("query_type") == "no_data":
                sync_push({"type": "error", "message": "Запрос относится к теме, по которой отсутствуют экономические данные."})
                return

            if extracted_params.get("needs_clarification"):
                q_list = extracted_params.get("clarifying_questions", [])
                sync_push({"type": "error", "message": f"Уточните запрос: {', '.join(q_list)}"})
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

            # ---------------------------------------------------------
            # ШАГ 2: ПОИСК (RAG) И РЕРАНКИНГ
            # ---------------------------------------------------------
            sync_push({"type": "log", "message": "🔍 Ищу источники в реестре НЦСЭД..."})
            candidates_original = search_datasets(query, top_k=20, index_path=FAISS_INDEX_PATH, metadata_path=METADATA_PATH)

            eng_query = _build_english_query(extracted_params)
            candidates_english = []
            if eng_query and eng_query.lower() not in query.lower():
                candidates_english = search_datasets(eng_query, top_k=20, index_path=FAISS_INDEX_PATH, metadata_path=METADATA_PATH)

            candidates = _merge_candidates(candidates_original, candidates_english)

            sync_push({"type": "log", "message": "🧠 Анализирую релевантность датасетов..."})
            top_datasets = rerank_datasets(query, candidates, top_k=5)

            best_score = max((d.get("rerank_score", 0.0) for d in top_datasets), default=0.0)
            if best_score < NO_DATA_RERANK_THRESHOLD:
                sync_push({"type": "error", "message": f"Нет релевантных данных (score: {best_score:.2f}). Переформулируйте запрос."})
                return

            sync_push({
                "type": "step_update", "step": 4, # Шаг источников в UI
                "artifact": {
                    "title": top_datasets[0].get('title'),
                    "tags": top_datasets[0].get('tags', []),
                    "description": top_datasets[0].get('description'),
                    "url": top_datasets[0].get('source_url', "#")
                }
            })

            # ---------------------------------------------------------
            # ШАГ 3: ДИЗАЙН ИССЛЕДОВАНИЯ
            # ---------------------------------------------------------
            sync_push({"type": "log", "message": "📝 Формирую гипотезы и дизайн..."})
            research_design = complete_json(build_research_design_messages(query, extracted_params, top_datasets))

            if db_state:
                db_state.design = research_design
                db.add(db_state)
                db.commit()

            sync_push({
                "type": "step_update", "step": 2, # Шаг Гипотез в UI
                "artifact": {
                    "hypotheses": [
                        {"id": i, "title": h.get('hypothesis'), "metrics": h.get('required_indicators', []), "selected": True}
                        for i, h in enumerate(research_design.get('hypotheses', []))
                    ]
                }
            })

            # ---------------------------------------------------------
            # ШАГ 4: ПЛАН СБОРКИ И ВАЛИДАЦИЯ
            # ---------------------------------------------------------
            sync_push({"type": "log", "message": "⚙️ Составляю план сборки данных..."})

            if archive_root:
                for ds in top_datasets:
                    fp = ds.get("file_path")
                    sid = str(ds.get("source_id") or "")
                    is_wb = "wb" in sid.lower() or str(fp or "").startswith("wb/")
                    if fp and not is_wb:
                        full_path = Path(archive_root) / fp
                        if full_path.exists():
                            ds["available_coverage"] = read_fedstatru_coverage(full_path)

            assembly_plan = complete_json(build_assembly_plan_messages(query, extracted_params, top_datasets, research_design))

            if db_state:
                db_state.assembly_plan = assembly_plan
                db.add(db_state)
                db.commit()

            if archive_root:
                sync_push({"type": "log", "message": "🛡️ Валидирую источники в локальном архиве..."})
                validation_errors = validate_assembly_plan(assembly_plan, archive_root=archive_root)
                if validation_errors:
                    sync_push({"type": "error", "message": f"Ошибка валидации плана: {validation_errors}"})
                    return

            # ---------------------------------------------------------
            # ШАГ 5: ГЕНЕРАЦИЯ КОДА (Codegen)
            # ---------------------------------------------------------
            sync_push({"type": "log", "message": "💻 Генерирую Python-скрипт..."})
            code = generate_analysis_code(query, research_design, top_datasets, archive_root=archive_root, assembly_plan=assembly_plan)

            if db_state:
                db_state.generated_script = code
                db_state.current_step = 6 # Дошли до скрипта
                db.add(db_state)
                db.commit()

            sync_push({
                "type": "step_update", "step": 5,
                "artifact": {"code": code}
            })

            # ---------------------------------------------------------
            # ШАГ 6: СБОРКА ДАННЫХ
            # ---------------------------------------------------------
            sync_push({"type": "log", "message": "✅ Завершаю сборку пайплайна..."})
            # Позже сюда добавится выполнение кода через Docker
            if db_state:
                db_state.result_data = {"rows": 0, "status": "Скрипт готов к запуску в песочнице"}
                db.add(db_state)
                db.commit()

            sync_push({
                "type": "step_update", "step": 6,
                "artifact": {"message": "Код успешно сгенерирован и прошел валидацию. Ожидание запуска.", "details": {}}
            })

            sync_push({"type": "done"})

        except Exception as e:
            sync_push({"type": "error", "message": f"Ошибка агента: {str(e)}"})
            if db_state:
                db_state.errors = db_state.errors or []
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
    main_loop = asyncio.get_running_loop()
    event_queues[task_id] = (asyncio.Queue(), main_loop)

    new_research = ResearchTable(
        session_id=task_id,
        query=query,
        user_id=user.id,
        trace=["Запуск задачи через API"]
    )
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