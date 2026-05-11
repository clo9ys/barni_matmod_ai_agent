"""Validate the output dataset produced by a generated analysis script."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


_METADATA_COLS = {"year", "country", "source", "extraction_date", "countryiso3", "region"}


def validate_output_dataset(
    csv_path: Path | str,
    expected_columns: list[str] | None = None,
    min_rows: int = 1,
) -> list[str]:
    """Return a list of validation error strings (empty = OK).

    Checks:
    - file exists and is readable
    - at least min_rows rows
    - all expected_columns are present
    - no indicator column is completely null
    """
    csv_path = Path(csv_path)
    errors: list[str] = []

    if not csv_path.exists():
        return [f"output_dataset.csv не найден: {csv_path}"]

    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:
        return [f"Не удалось прочитать CSV: {exc}"]

    if len(df) < min_rows:
        errors.append(f"Датасет слишком мал: {len(df)} строк (минимум {min_rows})")

    if expected_columns:
        missing = [c for c in expected_columns if c not in df.columns]
        if missing:
            errors.append(f"Отсутствуют ожидаемые колонки: {missing}")

    for col in df.columns:
        if col.lower() in _METADATA_COLS:
            continue
        if df[col].isna().all():
            errors.append(f"Колонка '{col}' полностью пустая")

    return errors


def output_validation_summary(
    result: dict[str, Any],
) -> dict[str, Any]:
    """Extract expected columns from assembly plan and run validate_output_dataset."""
    execution = result.get("execution") or {}
    csv_path = execution.get("output_csv")
    if not csv_path:
        return {"valid": False, "errors": ["скрипт не создал output_dataset.csv"]}

    plan = result.get("assembly_plan") or {}
    expected = [c["name"] for c in plan.get("output_columns", []) if "name" in c]

    errors = validate_output_dataset(csv_path, expected_columns=expected or None)
    return {"valid": len(errors) == 0, "errors": errors}
