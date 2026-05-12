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


def _timeframe_str(extracted_params: dict) -> str:
    tp = extracted_params.get("time_period") or {}
    start, end = tp.get("start"), tp.get("end")
    if start and end:
        return f"{start}-{end}" if start != end else str(start)
    return str(start or end) if (start or end) else "Не задано"


def _plan_artifact(assembly_plan: dict) -> dict:
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


def _execute_script(code: str, session_id: str, sync_push) -> dict | bool:
    """Run generated script, capture plots and CSV preview. Returns result dict or False."""
    import subprocess
    import re as _re

    sync_push({"type": "log", "message": "⚙️ Выполняю скрипт в локальной песочнице..."})

    outputs_root = Path(__file__).parent.parent.parent.parent / "data" / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    session_dir = outputs_root / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    output_csv = outputs_root / f"{session_id}.csv"
    script_path = outputs_root / f"script_{session_id}.py"

    # Override OUTPUT_DIR to session-specific folder so plots land there
    new_output_dir = f"OUTPUT_DIR = Path(r'{session_dir.absolute()}')"
    if _re.search(r'OUTPUT_DIR\s*=\s*Path\(', code):
        code = _re.sub(r'OUTPUT_DIR\s*=\s*Path\([^)]+\)', new_output_dir, code, count=1)
    else:
        code = f"from pathlib import Path\n{new_output_dir}\n{code}"

    injected = (
        f"{code}\n\nimport pandas as pd\n"
        "dfs = [v for v in locals().values() if isinstance(v, pd.DataFrame)]\n"
        "if dfs:\n"
        "    best_df = max(dfs, key=lambda x: len(x))\n"
        f"    best_df.to_csv(r'{output_csv.absolute()}', index=False)\n"
        "    print(f'SAVED_ROWS: {len(best_df)}')"
    )
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(injected)

    project_root = str(Path(__file__).parent.parent.parent.parent)
    _env = os.environ.copy()
    _env["PYTHONPATH"] = project_root
    _env["MPLBACKEND"] = "Agg"
    proc = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True, text=True, cwd=project_root, env=_env,
    )

    if proc.returncode != 0:
        sync_push({"type": "error", "message": f"Скрипт упал: {proc.stderr}"})
        return False

    rows_count = "Неизвестно"
    for line in proc.stdout.split("\n"):
        if "SAVED_ROWS:" in line:
            rows_count = line.split(":")[1].strip()

    plot_urls = [
        f"/api/v1/download/{session_id}/{p.name}"
        for p in sorted(session_dir.glob("*.png"))
    ]

    preview_columns: list = []
    preview_rows: list = []
    try:
        import pandas as _pd
        df = _pd.read_csv(output_csv, nrows=20)
        preview_columns = list(df.columns)
        preview_rows = df.fillna("").astype(str).to_dict("records")
    except Exception:
        pass

    return {
        "message": f"Сборка завершена! Собрано строк: {rows_count}",
        "file_url": f"/api/v1/download/{session_id}.csv",
        "plots": plot_urls,
        "preview_columns": preview_columns,
        "preview_rows": preview_rows,
    }


def run_agent_worker(task_id: str, query: str, user_id: int, loop: asyncio.AbstractEventLoop, skip_clarification: bool = False):
    def sync_push(data: dict):
        if task_id in event_queues:
            queue, main_loop = event_queues[task_id]
            asyncio.run_coroutine_threadsafe(queue.put(data), main_loop)

    with Session(engine) as db:
        db_state = db.exec(select(ResearchTable).where(ResearchTable.session_id == task_id)).first()

        def push_error(message: str):
            sync_push({"type": "error", "message": message})
            if db_state:
                db_state.errors = (db_state.errors or []) + [message]
                db.add(db_state); db.commit()

        try:
            if not is_llm_configured():
                raise RuntimeError("LLM не настроена. Укажите AI_API_KEY и AI_MODEL в .env")

            archive_root = os.getenv("ARCHIVE_ROOT", "")

            # ШАГ 1 — параметры запроса
            sync_push({"type": "log", "message": "🤖 Извлекаю параметры исследования..."})
            extracted_params = complete_json(build_extract_params_messages(query))
            if db_state:
                db_state.definition = extracted_params
                db.add(db_state); db.commit()

            if extracted_params.get("query_type") == "no_data":
                push_error("Тема вне компетенции агента.")
                return
            if extracted_params.get("query_type") == "no_coverage":
                push_error("По данной теме данные в реестре отсутствуют.")
                return

            questions = extracted_params.get("clarifying_questions", [])
            sync_push({"type": "step_update", "step": 1, "artifact": {
                "geography": ", ".join(extracted_params.get("geography", [])),
                "timeframe": _timeframe_str(extracted_params),
                "perspective": extracted_params.get("subject_area", "Экономика"),
                "questions": questions,
            }})

            if questions and not skip_clarification:
                sync_push({"type": "awaiting_clarification"})
                return

            # ШАГ 2 — поиск датасетов
            sync_push({"type": "log", "message": "🔍 Поиск в реестре НЦСЭД..."})
            candidates_ru = search_datasets(query, top_k=20, index_path=FULL_FAISS_INDEX_PATH, metadata_path=FULL_METADATA_PATH)
            english_query = _build_english_query(extracted_params)
            if english_query and english_query.lower() not in query.lower():
                candidates_en = search_datasets(english_query, top_k=20, index_path=FULL_FAISS_INDEX_PATH, metadata_path=FULL_METADATA_PATH)
            else:
                candidates_en = []
            top_datasets = rerank_datasets(english_query or query, _merge_candidates(candidates_ru, candidates_en), top_k=5)

            if not top_datasets or max((d.get("rerank_score", 0.0) for d in top_datasets), default=0.0) < NO_DATA_RERANK_THRESHOLD:
                push_error("Релевантные данные не найдены.")
                return

            sync_push({"type": "step_update", "step": 2, "artifact": {
                "title": top_datasets[0].get("title"),
                "tags": top_datasets[0].get("tags", []),
                "description": top_datasets[0].get("description"),
                "url": top_datasets[0].get("source_url", "#"),
            }})

            # ШАГ 3 — гипотезы
            sync_push({"type": "log", "message": "📝 Генерация гипотез..."})
            research_design = complete_json(build_research_design_messages(query, extracted_params, top_datasets))
            if db_state:
                db_state.design = research_design
                db.add(db_state); db.commit()
            sync_push({"type": "step_update", "step": 3, "artifact": {
                "hypotheses": [
                    {"id": i, "title": h.get("hypothesis"), "metrics": h.get("required_indicators", []), "selected": True}
                    for i, h in enumerate(research_design.get("hypotheses", []))
                ]
            }})

            # Обогащение Fedstat датасетов реальным покрытием периодов
            if archive_root:
                for ds in top_datasets:
                    fp = ds.get("file_path")
                    sid = str(ds.get("source_id") or "")
                    if fp and not ("wb" in sid.lower() or str(fp).startswith("wb/")):
                        full_path = Path(archive_root) / fp
                        if full_path.exists():
                            ds["available_coverage"] = read_fedstatru_coverage(full_path)

            # ШАГ 4 — план сборки
            sync_push({"type": "log", "message": "⚙️ Составляю план сборки данных..."})
            assembly_plan = complete_json(build_assembly_plan_messages(query, extracted_params, top_datasets, research_design))

            if isinstance(assembly_plan.get("primary_sources"), list):
                for src in assembly_plan["primary_sources"]:
                    for ds in top_datasets:
                        if src.get("dataset_id") == ds.get("id") and "file_path" in ds:
                            src["file_path"] = ds["file_path"]

            if db_state:
                db_state.assembly_plan = {"plan": assembly_plan, "sources": top_datasets}
                db.add(db_state); db.commit()

            if archive_root:
                errors = validate_assembly_plan(assembly_plan, archive_root=archive_root)
                if errors:
                    push_error(f"Ошибка валидации плана: {errors}")
                    return

            if not assembly_plan.get("primary_sources"):
                push_error("Не удалось определить источники данных. Попробуйте уточнить запрос.")
                return

            sync_push({"type": "step_update", "step": 4, "artifact": _plan_artifact(assembly_plan)})

            # ШАГ 5 — генерация кода
            sync_push({"type": "log", "message": "💻 Написание кода обработки..."})
            code = generate_analysis_code(query, research_design, top_datasets, archive_root=archive_root, assembly_plan=assembly_plan)
            if db_state:
                db_state.generated_script = code
                db_state.current_step = 5
                db.add(db_state); db.commit()
            sync_push({"type": "step_update", "step": 5, "artifact": {"code": code}})

            # ШАГ 6 — выполнение
            result_data = _execute_script(code, task_id, sync_push)
            if not result_data:
                return
            if db_state:
                db_state.result_data = result_data
                db_state.current_step = 6
                db.add(db_state); db.commit()
            sync_push({"type": "step_update", "step": 6, "artifact": result_data})
            sync_push({"type": "done"})

        except Exception as e:
            push_error(str(e))
        finally:
            if task_id in event_queues:
                del event_queues[task_id]


@router.post("/chat")
async def init_chat(request: Request, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    body = await request.json()
    query = body.get("query")
    skip_clarification = bool(body.get("skip_clarification", False))
    task_id = str(uuid.uuid4())
    main_loop = asyncio.get_running_loop()

    event_queues[task_id] = (asyncio.Queue(), main_loop)

    new_research = ResearchTable(session_id=task_id, query=query, user_id=user.id, trace=["Запуск"])
    db.add(new_research)
    db.commit()

    background_tasks.add_task(run_agent_worker, task_id, query, user.id, main_loop, skip_clarification)
    return {"task_id": task_id}


@router.get("/stream/{task_id}")
async def stream_task(request: Request, task_id: str, db: Session = Depends(get_session)):
    async def event_generator():
        # Ждём до 2с — воркер мог завершиться до подключения SSE
        for _ in range(20):
            if task_id in event_queues:
                break
            await asyncio.sleep(0.1)

        if task_id not in event_queues:
            task = db.exec(select(ResearchTable).where(ResearchTable.session_id == task_id)).first()
            if not task:
                yield {"data": json.dumps({"type": "error", "message": "Задача не найдена"})}
                return
            if task.current_step >= 6 and task.result_data:
                yield {"data": json.dumps({"type": "step_update", "step": 6, "artifact": task.result_data}, ensure_ascii=False)}
                yield {"data": json.dumps({"type": "done"})}
            elif task.errors:
                yield {"data": json.dumps({"type": "error", "message": task.errors[-1]})}
            else:
                yield {"data": json.dumps({"type": "error", "message": "Соединение потеряно, попробуйте снова"})}
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
async def get_history(user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    query = select(ResearchTable).where(ResearchTable.user_id == user.id).order_by(ResearchTable.created_at.desc())
    return db.exec(query).all()


@router.get("/research/{session_id}")
async def get_research_detail(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    res = db.exec(select(ResearchTable).where(ResearchTable.session_id == session_id, ResearchTable.user_id == user.id)).first()
    if not res:
        raise HTTPException(status_code=404)
    return res


@router.delete("/research/{session_id}")
async def delete_research(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    res = db.exec(select(ResearchTable).where(ResearchTable.session_id == session_id, ResearchTable.user_id == user.id)).first()
    if not res:
        raise HTTPException(status_code=404, detail="Исследование не найдено")
    db.delete(res)
    db.commit()

    output_dir = Path(__file__).parent.parent.parent.parent / "data" / "outputs"
    for path in [output_dir / f"{session_id}.csv", output_dir / f"script_{session_id}.py"]:
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass

    return {"status": "ok"}


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
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path=file_path, filename=filename, media_type="text/csv")
