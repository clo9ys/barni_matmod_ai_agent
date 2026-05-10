"""Validates assembly plan against actual parquet files on disk."""
from __future__ import annotations

import pathlib
from pathlib import Path
from typing import Any

import pandas as pd

from src.tools.readers import read_fedstatru_parquet, read_fedstatru_periods, read_wb_parquet


def _validate_fedstat_source(
    dataset_id: str,
    path: Path,
    filters: dict[str, Any],
    years_used: list[int],
    errors: list[str],
) -> None:
    okato = str(filters.get("okato") or "643")
    period = str(filters.get("period") or "62")
    years = years_used if years_used else None

    try:
        df = read_fedstatru_parquet(path, okato=okato, period=period, years=years)
    except Exception as exc:
        errors.append(f"[{dataset_id}] ошибка чтения файла: {exc}")
        return

    if df.empty:
        available = read_fedstatru_periods(path, okato)
        hint = f" (доступные периоды для ОКАТО={okato}: {available})" if available else ""
        errors.append(
            f"[{dataset_id}] нет строк с okato='{okato}' period='{period}' years={years_used}{hint}"
        )
        return

    if years_used:
        got = set(int(y) for y in df["year"].tolist())
        missing = sorted(set(years_used) - got)
        if missing:
            errors.append(
                f"[{dataset_id}] годы {missing} отсутствуют в файле (есть: {sorted(got)})"
            )


def _validate_wb_source(
    dataset_id: str,
    path: Path,
    filters: dict[str, Any],
    years_used: list[int],
    errors: list[str],
) -> None:
    countryiso3 = str(filters.get("countryiso3") or "RUS")
    years = years_used if years_used else None

    try:
        df = read_wb_parquet(path, countryiso3=countryiso3, years=years)
    except Exception as exc:
        errors.append(f"[{dataset_id}] ошибка чтения файла: {exc}")
        return

    if df.empty:
        errors.append(
            f"[{dataset_id}] нет строк с countryiso3='{countryiso3}' years={years_used}"
        )
        return

    if years_used:
        got = set(int(y) for y in df["year"].tolist())
        missing = sorted(set(years_used) - got)
        if missing:
            errors.append(
                f"[{dataset_id}] годы {missing} отсутствуют в файле (есть: {sorted(got)})"
            )


def validate_assembly_plan(
    assembly_plan: dict[str, Any],
    archive_root: str = "",
) -> list[str]:
    """Validate assembly plan against actual parquet files on disk.

    Returns list of validation error strings. Empty list means plan is valid.
    """
    errors: list[str] = []
    root = Path(archive_root) if archive_root else Path(".")

    for source in assembly_plan.get("primary_sources", []):
        dataset_id = source.get("dataset_id", "?")
        file_path = source.get("file_path")
        source_id = str(source.get("source_id") or "")
        filters = source.get("filters") or {}
        years_used = source.get("years_used") or []

        if not file_path:
            errors.append(f"[{dataset_id}] file_path отсутствует в плане сборки")
            continue

        full_path = root / file_path
        if not full_path.exists():
            errors.append(f"[{dataset_id}] файл не найден: {full_path}")
            continue

        is_wb = "wb" in source_id.lower() or str(file_path).startswith("wb/")
        if is_wb:
            _validate_wb_source(dataset_id, full_path, filters, years_used, errors)
        else:
            _validate_fedstat_source(dataset_id, full_path, filters, years_used, errors)

    return errors
