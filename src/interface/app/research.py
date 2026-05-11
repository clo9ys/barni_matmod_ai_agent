import os
import sys
import asyncio
import json
import queue as _queue
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
from src.tools.readers import read_fedstatru_coverage

router = APIRouter(tags=["research"])
event_queues: Dict[str, Tuple[asyncio.Queue, asyncio.AbstractEventLoop]] = {}
confirm_queues: Dict[str, _queue.Queue] = {}


def _pause_for_confirmation(task_id: str, sync_push, timeout: float = 3600.0) -> bool:
    """Pause the worker after a step and wait for user to click Continue or Cancel."""
    q: _queue.Queue = _queue.Queue()
    confirm_queues[task_id] = q
    sync_push({"type": "awaiting_confirmation"})
    try:
        signal = q.get(timeout=timeout)
        return signal == "continue"
    except _queue.Empty:
        return False
    finally:
        confirm_queues.pop(task_id, None)


def _timeframe_str(extracted_params: dict) -> str:
    tp = extracted_params.get("time_period") or {}
    start, end = tp.get("start"), tp.get("end")
    if start and end:
        return f"{start}-{end}" if start != end else str(start)
    return str(start or end) if (start or end) else "Не задано"


def _step1_artifact(extracted_params: dict) -> dict:
    return {
        "geography": ", ".join(extracted_params.get("geography", [])),
        "timeframe": _timeframe_str(extracted_params),
        "perspective": extracted_params.get("subject_area", "Экономика"),
        "questions": extracted_params.get("clarifying_questions", []),
    }


def _step2_artifact(top_datasets: list) -> dict:
    ds = top_datasets[0]
    return {
        "title": ds.get("title"),
        "tags": ds.get("tags", []),
        "description": ds.get("description"),
        "url": ds.get("source_url", "#"),
    }


def _step3_artifact(research_design: dict) -> dict:
    return {
        "hypotheses": [
            {"id": i, "title": h.get("hypothesis"), "metrics": h.get("required_indicators", []), "selected": True}
            for i, h in enumerate(research_design.get("hypotheses", []))
        ]
    }


def _step5_artifact(assembly_plan: dict) -> dict:
    """Format assembly plan details for display in step 5."""
    sources = [
        {
            "dataset_id": src.get("dataset_id"),
            "indicator": src.get("indicator_name") or src.get("indicator"),
            "years": src.get("years_used") or src.get("years"),
            "role": src.get("role", "primary"),
        }
        for src in assembly_plan.get("primary_sources", [])
    ]
    return {
        "combination_strategy": assembly_plan.get("combination_strategy"),
        "join_key": assembly_plan.get("join_key"),
        "output_columns": (assembly_plan.get("output_schema") or {}).get("columns") or assembly_plan.get("output_columns"),
        "sources": sources,
    }


def _run_step7(code: str, session_id: str, sync_push) -> bool:
    """Execute the generated script. Returns result dict on success, False on failure."""
    import subprocess
    import re as _re
    sync_push({"type": "log", "message": "⚙️ Выполняю скрипт в локальной песочнице..."})
    outputs_root = Path(__file__).parent.parent.parent.parent / "data" / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    session_output_dir = outputs_root / session_id
    session_output_dir.mkdir(parents=True, exist_ok=True)

    output_file = outputs_root / f"{session_id}.csv"
    script_path = outputs_root / f"script_{session_id}.py"

    # Override OUTPUT_DIR in generated code to session-specific folder
    new_output_dir = f"OUTPUT_DIR = Path(r'{session_output_dir.absolute()}')"
    if _re.search(r'OUTPUT_DIR\s*=\s*Path\(', code):
        code = _re.sub(r'OUTPUT_DIR\s*=\s*Path\([^)]+\)', new_output_dir, code, count=1)
    else:
        code = f"from pathlib import Path\n{new_output_dir}\n{code}"

    injected = (
        f"{code}\n\nimport pandas as pd\n"
        "dfs = [v for v in locals().values() if isinstance(v, pd.DataFrame)]\n"
        "if dfs:\n"
        "    best_df = max(dfs, key=lambda x: len(x))\n"
        f"    best_df.to_csv(r'{output_file.absolute()}', index=False)\n"
        "    print(f'SAVED_ROWS: {len(best_df)}')"
    )
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(injected)
    project_root = str(Path(__file__).parent.parent.parent.parent)
    _env = os.environ.copy()
    _env["PYTHONPATH"] = project_root
    _env["MPLBACKEND"] = "Agg"
    proc = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True, cwd=project_root, env=_env)
    if proc.returncode != 0:
        sync_push({"type": "error", "message": f"Скрипт упал: {proc.stderr}"})
        return False

    rows_count = "Неизвестно"
    for line in proc.stdout.split("\n"):
        if "SAVED_ROWS:" in line:
            rows_count = line.split(":")[1].strip()

    # Collect generated plot URLs
    plot_urls = [
        f"/api/v1/download/{session_id}/{png.name}"
        for png in sorted(session_output_dir.glob("*.png"))
    ]

    # CSV table preview (first 20 rows)
    preview_columns: list = []
    preview_rows: list = []
    try:
        import pandas as _pd
        df_preview = _pd.read_csv(output_file, nrows=20)
        preview_columns = list(df_preview.columns)
        preview_rows = df_preview.fillna("").astype(str).to_dict("records")
    except Exception:
        pass

    return {
        "message": f"Сборка завершена! Собрано строк: {rows_count}",
        "file_url": f"/api/v1/download/{session_id}.csv",
        "plots": plot_urls,
        "preview_columns": preview_columns,
        "preview_rows": preview_rows,
    }


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

            sync_push({"type": "step_update", "step": 1, "artifact": _step1_artifact(extracted_params)})
            if not _pause_for_confirmation(task_id, sync_push): return

            # ШАГ 2
            sync_push({"type": "log", "message": "🔍 Поиск в реестре НЦСЭД..."})
            candidates_ru = search_datasets(query, top_k=20, index_path=FULL_FAISS_INDEX_PATH, metadata_path=FULL_METADATA_PATH)
            english_query = _build_english_query(extracted_params)
            if english_query and english_query.lower() not in query.lower():
                candidates_en = search_datasets(english_query, top_k=20, index_path=FULL_FAISS_INDEX_PATH, metadata_path=FULL_METADATA_PATH)
            else:
                candidates_en = []
            candidates = _merge_candidates(candidates_ru, candidates_en)
            rerank_query = english_query if english_query else query
            top_datasets = rerank_datasets(rerank_query, candidates, top_k=5)

            if not top_datasets or max((d.get("rerank_score", 0.0) for d in top_datasets), default=0.0) < NO_DATA_RERANK_THRESHOLD:
                sync_push({"type": "error", "message": "Релевантные данные не найдены."})
                return

            sync_push({"type": "step_update", "step": 2, "artifact": _step2_artifact(top_datasets)})
            if not _pause_for_confirmation(task_id, sync_push): return

            # ШАГ 3
            sync_push({"type": "log", "message": "📝 Генерация гипотез..."})
            research_design = complete_json(build_research_design_messages(query, extracted_params, top_datasets))
            if db_state:
                db_state.design = research_design
                db.add(db_state)
                db.commit()
            sync_push({"type": "step_update", "step": 3, "artifact": _step3_artifact(research_design)})
            if not _pause_for_confirmation(task_id, sync_push): return

            # ШАГ 3.5 — обогащение Fedstat датасетов реальным покрытием периодов
            if archive_root:
                for ds in top_datasets:
                    fp = ds.get("file_path")
                    sid = str(ds.get("source_id") or "")
                    is_wb = "wb" in sid.lower() or str(fp or "").startswith("wb/")
                    if fp and not is_wb:
                        full_path = Path(archive_root) / fp
                        if full_path.exists():
                            ds["available_coverage"] = read_fedstatru_coverage(full_path)

            # ШАГ 4
            sync_push({"type": "log", "message": "⚙️ Составление плана сборки..."})
            assembly_plan = complete_json(build_assembly_plan_messages(query, extracted_params, top_datasets, research_design))

            if isinstance(assembly_plan.get("primary_sources"), list):
                for plan_source in assembly_plan["primary_sources"]:
                    for ds in top_datasets:
                        if plan_source.get("dataset_id") == ds.get("id") and "file_path" in ds:
                            plan_source["file_path"] = ds.get("file_path")

            if db_state:
                db_state.assembly_plan = {"plan": assembly_plan, "sources": top_datasets}
                db.add(db_state)
                db.commit()

            if archive_root:
                errors = validate_assembly_plan(assembly_plan, archive_root=archive_root)
                if errors:
                    sync_push({"type": "error", "message": f"Ошибка валидации плана: {errors}"})
                    return

            if not assembly_plan.get("primary_sources"):
                sync_push({"type": "error", "message": "Не удалось определить источники данных для этого запроса. Попробуйте уточнить тему или период."})
                return

            # ШАГ 4 — детали плана сборки
            sync_push({"type": "log", "message": "📋 Формирую детали плана сборки..."})
            sync_push({"type": "step_update", "step": 4, "artifact": _step5_artifact(assembly_plan)})
            if not _pause_for_confirmation(task_id, sync_push): return

            # ШАГ 5 — генерация кода
            sync_push({"type": "log", "message": "💻 Написание кода обработки..."})
            code = generate_analysis_code(query, research_design, top_datasets, archive_root=archive_root, assembly_plan=assembly_plan)

            if db_state:
                db_state.generated_script = code
                db_state.current_step = 6
                db.add(db_state)
                db.commit()

            sync_push({"type": "step_update", "step": 5, "artifact": {"code": code}})
            if not _pause_for_confirmation(task_id, sync_push): return

            # ШАГ 6 — выполнение скрипта
            result_data = _run_step7(code, task_id, sync_push)
            if not result_data:
                return
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


def run_refine_worker(stream_id: str, session_id: str, from_step: int, correction: str, loop: asyncio.AbstractEventLoop):
    def sync_push(data: dict):
        if stream_id in event_queues:
            queue, main_loop = event_queues[stream_id]
            asyncio.run_coroutine_threadsafe(queue.put(data), main_loop)

    with Session(engine) as db:
        db_state = db.exec(select(ResearchTable).where(ResearchTable.session_id == session_id)).first()
        if not db_state:
            sync_push({"type": "error", "message": "Сессия не найдена"})
            return

        try:
            archive_root = os.getenv("ARCHIVE_ROOT", "")
            query = db_state.query
            effective_query = f"{query}\n\nУточнение пользователя: {correction}" if correction else query

            # Restore saved state for steps we're skipping
            extracted_params = db_state.definition or {}
            top_datasets = (db_state.assembly_plan or {}).get("sources", [])
            research_design = db_state.design or {}
            assembly_plan_data = (db_state.assembly_plan or {}).get("plan", {})

            if from_step <= 1:
                sync_push({"type": "log", "message": "🤖 Уточняю параметры исследования..."})
                extracted_params = complete_json(build_extract_params_messages(effective_query))
                db_state.definition = extracted_params
                db.add(db_state); db.commit()
                sync_push({"type": "step_update", "step": 1, "artifact": _step1_artifact(extracted_params)})
                if not _pause_for_confirmation(stream_id, sync_push): return

            if from_step <= 2:
                sync_push({"type": "log", "message": "🔍 Уточнённый поиск в реестре..."})
                candidates_ru = search_datasets(effective_query, top_k=20, index_path=FULL_FAISS_INDEX_PATH, metadata_path=FULL_METADATA_PATH)
                english_query = _build_english_query(extracted_params)
                if english_query and english_query.lower() not in effective_query.lower():
                    candidates_en = search_datasets(english_query, top_k=20, index_path=FULL_FAISS_INDEX_PATH, metadata_path=FULL_METADATA_PATH)
                else:
                    candidates_en = []
                rerank_q = english_query if english_query else effective_query
                top_datasets = rerank_datasets(rerank_q, _merge_candidates(candidates_ru, candidates_en), top_k=5)
                if not top_datasets:
                    sync_push({"type": "error", "message": "Релевантные данные не найдены."})
                    return
                db_state.assembly_plan = {**(db_state.assembly_plan or {}), "sources": top_datasets}
                db.add(db_state); db.commit()
                sync_push({"type": "step_update", "step": 2, "artifact": _step2_artifact(top_datasets)})
                if not _pause_for_confirmation(stream_id, sync_push): return

            if from_step <= 3:
                sync_push({"type": "log", "message": "📝 Уточнение гипотез..."})
                research_design = complete_json(build_research_design_messages(effective_query, extracted_params, top_datasets))
                db_state.design = research_design
                db.add(db_state); db.commit()
                sync_push({"type": "step_update", "step": 3, "artifact": _step3_artifact(research_design)})
                if not _pause_for_confirmation(stream_id, sync_push): return

            if from_step <= 3 or (from_step <= 4 and not any(ds.get("available_coverage") for ds in top_datasets)):
                if archive_root:
                    for ds in top_datasets:
                        fp = ds.get("file_path")
                        sid = str(ds.get("source_id") or "")
                        is_wb = "wb" in sid.lower() or str(fp or "").startswith("wb/")
                        if fp and not is_wb:
                            full_path = Path(archive_root) / fp
                            if full_path.exists():
                                ds["available_coverage"] = read_fedstatru_coverage(full_path)

            if from_step <= 4:
                sync_push({"type": "log", "message": "⚙️ Уточнение плана сборки..."})
                assembly_plan_data = complete_json(build_assembly_plan_messages(effective_query, extracted_params, top_datasets, research_design))
                if isinstance(assembly_plan_data.get("primary_sources"), list):
                    for ps in assembly_plan_data["primary_sources"]:
                        for ds in top_datasets:
                            if ps.get("dataset_id") == ds.get("id") and "file_path" in ds:
                                ps["file_path"] = ds["file_path"]
                db_state.assembly_plan = {"plan": assembly_plan_data, "sources": top_datasets}
                db.add(db_state); db.commit()
                if archive_root:
                    errors = validate_assembly_plan(assembly_plan_data, archive_root=archive_root)
                    if errors:
                        sync_push({"type": "error", "message": f"Ошибка валидации плана: {errors}"})
                        return
                if not assembly_plan_data.get("primary_sources"):
                    sync_push({"type": "error", "message": "Не удалось определить источники данных для этого запроса. Попробуйте уточнить тему или период."})
                    return
                sync_push({"type": "step_update", "step": 4, "artifact": _step5_artifact(assembly_plan_data)})
                if not _pause_for_confirmation(stream_id, sync_push): return

            if from_step <= 5:
                sync_push({"type": "log", "message": "💻 Уточнение кода обработки..."})
                code = generate_analysis_code(effective_query, research_design, top_datasets, archive_root=archive_root, assembly_plan=assembly_plan_data)
                db_state.generated_script = code
                db_state.current_step = 6
                db.add(db_state); db.commit()
                sync_push({"type": "step_update", "step": 5, "artifact": {"code": code}})
                if not _pause_for_confirmation(stream_id, sync_push): return

                result_data = _run_step7(code, session_id, sync_push)
                if not result_data:
                    return
                db_state.result_data = result_data
                db.add(db_state); db.commit()
                sync_push({"type": "step_update", "step": 6, "artifact": result_data})

            sync_push({"type": "done"})

        except Exception as e:
            sync_push({"type": "error", "message": str(e)})
        finally:
            if stream_id in event_queues:
                del event_queues[stream_id]


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
    return {"task_id": task_id, "session_id": task_id}


@router.post("/research/{session_id}/refine")
async def refine_research(session_id: str, request: Request, background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    body = await request.json()
    from_step = int(body.get("from_step", 1))
    correction = body.get("correction", "").strip()

    stream_id = str(uuid.uuid4())
    main_loop = asyncio.get_running_loop()
    event_queues[stream_id] = (asyncio.Queue(), main_loop)

    background_tasks.add_task(run_refine_worker, stream_id, session_id, from_step, correction, main_loop)
    return {"task_id": stream_id}


@router.post("/stream/{task_id}/continue")
async def continue_task(task_id: str, user: User = Depends(get_current_user)):
    if task_id in confirm_queues:
        confirm_queues[task_id].put("continue")
    return {"ok": True}


@router.post("/stream/{task_id}/cancel")
async def cancel_task(task_id: str, user: User = Depends(get_current_user)):
    if task_id in confirm_queues:
        confirm_queues[task_id].put("cancel")
    return {"ok": True}


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
                try:
                    event_data = await asyncio.wait_for(queue.get(), timeout=10.0)
                    yield {"data": json.dumps(event_data, ensure_ascii=False)}
                    if event_data.get("type") in ["done", "error"]:
                        break
                except asyncio.TimeoutError:
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
    if not res:
        raise HTTPException(status_code=404)
    return res


@router.get("/download/{session_id}/{filename}")
async def download_session_file(session_id: str, filename: str):
    file_path = Path(f"data/outputs/{session_id}/{filename}")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path=file_path, filename=filename)


@router.get("/download/{filename}")
async def download_file(filename: str):
    file_path = Path(f"data/outputs/{filename}")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл датасета не найден")
    return FileResponse(path=file_path, filename=filename, media_type='text/csv')
