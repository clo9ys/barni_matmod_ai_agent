from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.ml.model import complete_text
from src.ml.prompts import build_codegen_messages


def generate_analysis_code(
    user_query: str,
    research_design: dict[str, Any],
    datasets: list[dict[str, Any]],
    archive_root: str = "",
    assembly_plan: dict[str, Any] | None = None,
    output_dir: str = "",
) -> str:
    messages = build_codegen_messages(
        user_query,
        research_design,
        datasets,
        archive_root=archive_root,
        assembly_plan=assembly_plan,
        output_dir=output_dir,
    )
    code = complete_text(messages, temperature=0.1, max_tokens=4000)
    code = _strip_markdown_fences(code)
    code = _fix_wb_paths(code, assembly_plan or {}, archive_root=archive_root)
    return code


def _norm(stem: str) -> str:
    """Normalize WB indicator stem: lowercase, dots/dashes → underscore."""
    return re.sub(r"[.\-]", "_", stem.lower())


def _fix_wb_paths(code: str, assembly_plan: dict[str, Any], archive_root: str = "") -> str:
    """Rewrite any wb/parquet/xxx.parquet string literal to the correct filename.

    LLMs derive filenames from dataset_id (e.g. ny_gdp_mktp_cd.parquet) instead of
    using the real name on disk (NY.GDP.MKTP.CD.parquet). This post-processor builds
    a normalized stem → correct_path index from two sources:

      1. Actual files on disk at archive_root/wb/parquet/ — catches everything,
         including WB files the LLM added that are outside the assembly plan.
      2. assembly_plan primary_sources — fallback when archive_root is empty.
    """
    stem_to_path: dict[str, str] = {}

    # Source 1: real files on disk (most reliable)
    if archive_root:
        wb_dir = Path(archive_root) / "wb" / "parquet"
        if wb_dir.is_dir():
            for f in wb_dir.iterdir():
                if f.suffix == ".parquet":
                    stem_to_path[_norm(f.stem)] = f"wb/parquet/{f.name}"

    # Source 2: assembly plan (fallback)
    for src in assembly_plan.get("primary_sources", []):
        fp = src.get("file_path", "")
        if fp.startswith("wb/parquet/") and fp.endswith(".parquet"):
            stem = fp[len("wb/parquet/"):-len(".parquet")]
            key = _norm(stem)
            if key not in stem_to_path:
                stem_to_path[key] = fp

    if not stem_to_path:
        return code

    def replace_match(m: re.Match) -> str:
        quote, found = m.group(1), m.group(2)
        correct = stem_to_path.get(_norm(found[:-len(".parquet")]))
        return f"{quote}{correct}{quote}" if correct else m.group(0)

    return re.sub(r'(["\'])wb/parquet/([^"\']+\.parquet)\1', replace_match, code)


def _strip_markdown_fences(code: str) -> str:
    """Remove ```python ... ``` or ``` ... ``` wrappers that LLMs sometimes add."""
    lines = code.strip().splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)
