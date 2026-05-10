from __future__ import annotations

from typing import Any

from src.ml.model import complete_text
from src.ml.prompts import build_codegen_messages


def generate_analysis_code(
    user_query: str,
    research_design: dict[str, Any],
    datasets: list[dict[str, Any]],
    archive_root: str = "",
    assembly_plan: dict[str, Any] | None = None,
) -> str:
    messages = build_codegen_messages(
        user_query,
        research_design,
        datasets,
        archive_root=archive_root,
        assembly_plan=assembly_plan,
    )
    return complete_text(messages, temperature=0.1, max_tokens=4000)
