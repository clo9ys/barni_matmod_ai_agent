"""Save pipeline artifacts to outputs/<session_id>/."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def make_session_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _save_json(path: Path, data: Any) -> None:
    if data is None:
        return
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def save_artifacts(
    result: dict[str, Any],
    session_id: str,
    outputs_root: Path | str = "outputs",
) -> Path:
    """Save all pipeline artifacts to outputs/<session_id>/. Returns session dir."""
    session_dir = Path(outputs_root) / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    _save_json(session_dir / "research_definition.json", result.get("extracted_params"))
    _save_json(session_dir / "retrieved_datasets.json", result.get("retrieved_datasets"))
    _save_json(session_dir / "reranked_datasets.json", result.get("datasets"))
    _save_json(session_dir / "research_design.json", result.get("research_design"))
    _save_json(session_dir / "assembly_plan.json", result.get("assembly_plan"))

    # dataset_structure — extracted from research_design without extra LLM call
    rd = result.get("research_design") or {}
    _save_json(session_dir / "dataset_structure.json", rd.get("target_dataset_structure"))

    _save_json(session_dir / "validation_report.json", {
        "status": result.get("status"),
        "errors": result.get("validation_errors", []),
    })

    code = result.get("code")
    if code:
        (session_dir / "generated_script.py").write_text(code, encoding="utf-8")

    return session_dir
