import os
import sys
import asyncio
import json
import uuid
from pathlib import Path
from fastapi.responses import FileResponse
from typing import Dict, Tuple
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlmodel import Session, select
from sse_starlette.sse import EventSourceResponse
from src.core.database import ResearchTable, User, get_session, engine
from src.interface.app.auth import get_current_user

from src.ml.model import complete_json, is_llm_configured
from src.ml.prompts import build_extract_params_messages, build_research_design_messages, build_assembly_plan_messages
from src.ml.rag import FULL_FAISS_INDEX_PATH, FULL_METADATA_PATH, search_datasets
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

            # ШАГ 1
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

            # ШАГ 2
            sync_push({"type": "log", "message": "🔍 Поиск в реестре НЦСЭД..."})
            candidates_ru = search_datasets(query, top_k=20, index_path=FULL_FAISS_INDEX_PATH, metadata_path=FULL_METADATA_PATH)
            english_query = _build_english_query(extracted_params)
            if english_query and english_query.lower() not in query.lower():
                candidates_en = search_datasets(english_query, top_k=20, index_path=FULL_FAISS_INDEX_PATH, metadata_path=FULL_METADATA_PATH)
            else:
                candidates_en = []
            candidates = _merge_candidates(candidates_ru, candidates_en)
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

            # ШАГ 3
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

            # ШАГ 4
            sync_push({"type": "log", "message": "⚙️ Составление плана сборки..."})
            assembly_plan = complete_json(build_assembly_plan_messages(query, extracted_params, top_datasets, research_design))

            if isinstance(assembly_plan.get("sources"), list):
                for plan_source in assembly_plan["sources"]:
                    for ds in top_datasets:
                        if plan_source.get("id") == ds.get("id") and "file_path" in ds:
                            plan_source["file_path"] = ds.get("file_path")

            if db_state:
                db_state.assembly_plan = {"plan": assembly_plan, "sources": top_datasets}
                db.add(db_state)
                db.commit()

            if archive_root:
                errors = validate_assembly_plan(assembly_plan, archive_root=archive_root)
                if errors:
                    sync_push({"type": "log", "message": "⚠️ Валидация не прошла, исправляю план..."})
                    assembly_plan = complete_json(build_assembly_plan_messages(
                        query, extracted_params, top_datasets, research_design,
                        validation_errors=errors,
                    ))
                    errors = validate_assembly_plan(assembly_plan, archive_root=archive_root)
                if errors:
                    sync_push({"type": "error", "message": f"Ошибка валидации плана: {errors}"})
                    return

            sync_push({"type": "step_update", "step": 4, "artifact": {"plan": "Валидация пройдена"}})

            # ШАГ 5
            sync_push({"type": "log", "message": "💻 Написание кода обработки..."})
            code = generate_analysis_code(query, research_design, top_datasets, archive_root=archive_root, assembly_plan=assembly_plan)

            if db_state:
                db_state.generated_script = code
                db_state.current_step = 6
                db.add(db_state)
                db.commit()

            sync_push({"type": "step_update", "step": 5, "artifact": {"code": code}})

            # ШАГ 6
            sync_push({"type": "log", "message": "⚙️ Выполняю скрипт в локальной песочнице..."})

            output_dir = Path(__file__).parent.parent.parent.parent / "data" / "outputs"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{task_id}.csv"
            script_path = output_dir / f"script_{task_id}.py"

            injected_code = f"{code}\n\nimport pandas as pd\ndfs = [v for v in locals().values() if isinstance(v, pd.DataFrame)]\nif dfs:\n    best_df = max(dfs, key=lambda x: len(x))\n    best_df.to_csv(r'{str(output_file.absolute())}', index=False)\n    print(f'SAVED_ROWS: {{len(best_df)}}')"

            with open(script_path, "w", encoding="utf-8") as f:
                f.write(injected_code)

            import subprocess
            project_root = str(Path(__file__).parent.parent.parent.parent)
            _env = os.environ.copy()
            _env["PYTHONPATH"] = project_root
            _env["MPLBACKEND"] = "Agg"
            process = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                cwd=project_root,
                env=_env,
            )

            if process.returncode != 0:
                # Теперь, если код сгенерировался с ошибкой, мы увидим её на фронтенде
                sync_push({"type": "error", "message": f"Скрипт упал: {process.stderr}"})
                return

            rows_count = "Неизвестно"
            for line in process.stdout.split("\n"):
                if "SAVED_ROWS:" in line:
                    rows_count = line.split(":")[1].strip()

            result_data = {
                "message": f"Сборка завершена! Собрано строк: {rows_count}",
                "file_url": f"/api/v1/download/{task_id}.csv"
            }

            if db_state:
                db_state.result_data = result_data
                db.add(db_state)
                db.commit()

            sync_push({"type": "step_update", "step": 6, "artifact": result_data})
            sync_push({"type": "done"})

        except Exception as e:
            sync_push({"type": "error", "message": str(e)})
        finally:
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
                if await request.is_disconnected(): break
                try:
                    # ФИКС 1: Механизм анти-таймаута
                    # Ждем ответ 10 секунд. Если модель еще думает, кидаем пинг.
                    event_data = await asyncio.wait_for(queue.get(), timeout=10.0)
                    yield {"data": json.dumps(event_data, ensure_ascii=False)}
                    if event_data.get("type") in ["done", "error"]: break
                except asyncio.TimeoutError:
                    # Пинг-сообщение не дает браузеру оборвать соединение
                    yield {"data": json.dumps({"type": "ping"})}
        except Exception:
            pass
    return EventSourceResponse(event_generator())

@router.get("/history")
async def get_history(user: User = Depends(get_current_user)):
    return user.researches

@router.get("/research/{session_id}")
async def get_research_detail(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    res = db.exec(select(ResearchTable).where(ResearchTable.session_id == session_id, ResearchTable.user_id == user.id)).first()
    if not res: raise HTTPException(status_code=404)
    return res

@router.get("/download/{filename}")
async def download_file(filename: str):
    file_path = Path(f"data/outputs/{filename}")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл датасета не найден")
    return FileResponse(path=file_path, filename=filename, media_type='text/csv')