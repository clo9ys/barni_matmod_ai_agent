from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.ml.codegen import generate_analysis_code
from src.ml.model import complete_json, is_llm_configured
from src.ml.prompts import (
    build_assembly_plan_messages,
    build_extract_params_messages,
    build_research_design_messages,
)
from src.ml.rag import (
    FAISS_INDEX_PATH,
    FULL_FAISS_INDEX_PATH,
    FULL_METADATA_PATH,
    METADATA_PATH,
    search_datasets,
)
from src.ml.reranker import rerank_datasets
from src.tools.readers import read_fedstatru_coverage
from src.tools.validator import validate_assembly_plan
from src.core.artifacts import make_session_id, save_artifacts, _save_json
from src.core.executor import run_script
from src.tools.output_validator import output_validation_summary


def _build_english_query(extracted_params: dict[str, Any]) -> str:
    """Build an English search query from structured extracted params.

    Prefers the LLM-generated english_query field; falls back to concatenating
    raw indicators and geography (which may still be in Russian).
    """
    if extracted_params.get("english_query"):
        return str(extracted_params["english_query"])
    parts: list[str] = []
    parts.extend(extracted_params.get("indicators") or [])
    parts.extend(extracted_params.get("geography") or [])
    tp = extracted_params.get("time_period") or {}
    if tp.get("start") and tp.get("end"):
        parts.append(f"{tp['start']}-{tp['end']}")
    parts.extend(extracted_params.get("units") or [])
    return " ".join(str(p) for p in parts if p)


def _merge_candidates(
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge two candidate lists, keeping the highest FAISS score per dataset id."""
    seen: dict[str, dict[str, Any]] = {}
    for item in primary + secondary:
        did = item.get("id", "")
        if did not in seen or item.get("score", 0) > seen[did].get("score", 0):
            seen[did] = item
    # Sort by score descending
    return sorted(seen.values(), key=lambda x: x.get("score", 0), reverse=True)


# Minimum rerank score for any dataset to be considered relevant.
# If the best candidate is below this threshold, we treat it as no_data.
NO_DATA_RERANK_THRESHOLD = 0.05  # cross-encoder sigmoid scores are low by nature; FAISS is the primary quality gate


def run(
    user_query: str,
    *,
    top_k_retrieval: int = 20,
    top_k_rerank: int = 5,
    generate_code: bool = True,
    execute_code: bool = False,
    use_full_registry: bool = False,
    save_outputs: bool = True,
) -> dict[str, Any]:
    """Full pipeline: query → params → retrieval → rerank → design → code.

    Returns a dict that always contains:
        status: "ok" | "needs_clarification" | "no_data"
        query: original user query
        extracted_params: structured params from step 1

    When status == "needs_clarification":
        clarifying_questions: list[str]   — questions to show the user

    When status == "no_data":
        reason: str                        — human-readable explanation

    When status == "ok":
        datasets, research_design, code (if generate_code=True)
    """
    if not is_llm_configured():
        raise RuntimeError("LLM not configured. Set AI_API_KEY and AI_MODEL in .env")

    session_id = make_session_id()
    archive_root = os.getenv("ARCHIVE_ROOT", "")
    outputs_root = os.getenv("OUTPUTS_ROOT", "outputs")

    index_path: Path
    metadata_path: Path
    if use_full_registry:
        index_path = FULL_FAISS_INDEX_PATH
        metadata_path = FULL_METADATA_PATH
    else:
        index_path = FAISS_INDEX_PATH
        metadata_path = METADATA_PATH

    # Step 1: Formalize the query into structured parameters
    extracted_params = complete_json(
        build_extract_params_messages(user_query),
    )

    base_result: dict[str, Any] = {
        "query": user_query,
        "extracted_params": extracted_params,
    }

    # Stop 1: LLM flagged the query as no_data (topic outside economic statistics)
    if extracted_params.get("query_type") == "no_data":
        return {
            **base_result,
            "status": "no_data",
            "reason": (
                "Запрос относится к теме, по которой экономические данные отсутствуют "
                "или не могут быть получены из доступных источников."
            ),
        }

    # Stop 2: query is ambiguous and LLM produced clarifying questions
    if extracted_params.get("needs_clarification"):
        questions = extracted_params.get("clarifying_questions") or []
        return {
            **base_result,
            "status": "needs_clarification",
            "clarifying_questions": questions,
        }

    # Step 2: Dual-language semantic retrieval
    candidates_original = search_datasets(
        user_query,
        top_k=top_k_retrieval,
        index_path=index_path,
        metadata_path=metadata_path,
    )

    english_query = _build_english_query(extracted_params)
    if english_query and english_query.lower() not in user_query.lower():
        candidates_english = search_datasets(
            english_query,
            top_k=top_k_retrieval,
            index_path=index_path,
            metadata_path=metadata_path,
        )
    else:
        candidates_english = []

    candidates = _merge_candidates(candidates_original, candidates_english)

    # Step 3: Rerank with LLM — narrow down to top_k_rerank
    top_datasets = rerank_datasets(user_query, candidates, top_k=top_k_rerank)
    base_result["retrieved_datasets"] = candidates

    # Stop 3: no dataset scored above the relevance threshold
    best_score = max((d.get("rerank_score", 0.0) for d in top_datasets), default=0.0)
    if best_score < NO_DATA_RERANK_THRESHOLD:
        return {
            **base_result,
            "status": "no_data",
            "datasets": top_datasets,
            "reason": (
                f"Ни один из найденных датасетов не набрал достаточный балл релевантности "
                f"(лучший: {best_score:.2f}, порог: {NO_DATA_RERANK_THRESHOLD}). "
                "Попробуйте переформулировать запрос или уточнить географию / период."
            ),
        }

    # Step 4: Generate research design
    research_design = complete_json(
        build_research_design_messages(user_query, extracted_params, top_datasets),
    )

    # Step 4.5: Enrich Fedstat datasets with real period+year coverage from parquet files
    if archive_root:
        for ds in top_datasets:
            fp = ds.get("file_path")
            sid = str(ds.get("source_id") or "")
            is_wb = "wb" in sid.lower() or str(fp or "").startswith("wb/")
            if fp and not is_wb:
                full_path = Path(archive_root) / fp
                if full_path.exists():
                    ds["available_coverage"] = read_fedstatru_coverage(full_path)

    # Step 5: Generate assembly plan — explicit data sourcing decisions
    assembly_plan = complete_json(
        build_assembly_plan_messages(user_query, extracted_params, top_datasets, research_design),
    )

    # Step 5.5: Validate assembly plan against local archive
    if archive_root:
        validation_errors = validate_assembly_plan(assembly_plan, archive_root=archive_root)
        if validation_errors:
            return {
                **base_result,
                "status": "validation_failed",
                "datasets": top_datasets,
                "research_design": research_design,
                "assembly_plan": assembly_plan,
                "validation_errors": validation_errors,
            }

    result: dict[str, Any] = {
        **base_result,
        "status": "ok",
        "datasets": top_datasets,
        "research_design": research_design,
        "assembly_plan": assembly_plan,
    }

    # Step 6: Generate Python analysis code
    if generate_code:
        script_output_dir = str(Path(outputs_root) / session_id)
        result["code"] = generate_analysis_code(
            user_query,
            research_design,
            top_datasets,
            archive_root=archive_root,
            assembly_plan=assembly_plan,
            output_dir=script_output_dir,
        )

    result["session_id"] = session_id

    if save_outputs:
        session_dir = save_artifacts(result, session_id, outputs_root)
        result["session_dir"] = str(session_dir)

        # Step 7: Execute the generated script
        if execute_code and result.get("code"):
            execution = run_script(session_dir)
            result["execution"] = {
                "success": execution.success,
                "returncode": execution.returncode,
                "stdout": execution.stdout,
                "stderr": execution.stderr,
                "errors": execution.errors,
                "output_csv": str(execution.output_csv) if execution.output_csv else None,
                "output_meta": str(execution.output_meta) if execution.output_meta else None,
            }

            # Step 7.5: Validate the output dataset
            output_check = output_validation_summary(result)
            result["execution"]["output_valid"] = output_check["valid"]
            result["execution"]["output_validation_errors"] = output_check["errors"]

            _save_json(
                session_dir / "output_validation.json",
                output_check,
            )

    return result
