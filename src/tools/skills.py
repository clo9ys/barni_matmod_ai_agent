"""Pre-built data transformation primitives for generated analysis scripts.

LLM assembles scripts from these verified functions instead of writing
arbitrary pandas code from scratch.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd


def rename_value_column(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Rename the 'value' column to a meaningful indicator name."""
    return df.rename(columns={"value": name})


def filter_years(
    df: pd.DataFrame,
    years: list[int],
    year_col: str = "year",
) -> pd.DataFrame:
    """Keep only rows where year_col is in years."""
    return df[df[year_col].isin(years)].reset_index(drop=True)


def _drop_duplicate_cols(left: pd.DataFrame, right: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Drop columns from right that already exist in left (excluding join keys)."""
    overlap = set(left.columns) & set(right.columns) - set(keys)
    return right.drop(columns=list(overlap)) if overlap else right


def join_on_year(*dfs: pd.DataFrame, how: str = "outer") -> pd.DataFrame:
    """Outer-join multiple DataFrames on the 'year' column."""
    if not dfs:
        return pd.DataFrame()
    result = dfs[0]
    for df in dfs[1:]:
        result = result.merge(_drop_duplicate_cols(result, df, ["year"]), on="year", how=how)
    return result.sort_values("year").reset_index(drop=True)


def join_on_country_year(
    *dfs: pd.DataFrame,
    country_col: str = "country",
    how: str = "outer",
) -> pd.DataFrame:
    """Outer-join multiple DataFrames on (country_col, 'year')."""
    if not dfs:
        return pd.DataFrame()
    keys = [country_col, "year"]
    result = dfs[0]
    for df in dfs[1:]:
        result = result.merge(_drop_duplicate_cols(result, df, keys), on=keys, how=how)
    return result.sort_values(keys).reset_index(drop=True)


def calculate_index_to_base(
    df: pd.DataFrame,
    base_year: int,
    value_col: str = "value",
    index_col: str | None = None,
) -> pd.DataFrame:
    """Add a column with values re-indexed so base_year = 100."""
    base_rows = df.loc[df["year"] == base_year, value_col]
    if base_rows.empty:
        raise ValueError(f"base_year={base_year} not found in DataFrame")
    base_value = base_rows.iloc[0]
    if base_value == 0:
        raise ValueError(f"base value for year={base_year} is zero, cannot index")
    out_col = index_col or f"{value_col}_index_{base_year}"
    df = df.copy()
    df[out_col] = df[value_col] / base_value * 100
    return df


def calculate_per_capita(
    df: pd.DataFrame,
    value_col: str,
    population_col: str,
    result_col: str | None = None,
) -> pd.DataFrame:
    """Add a per-capita column: value_col / population_col."""
    out_col = result_col or f"{value_col}_per_capita"
    df = df.copy()
    df[out_col] = df[value_col] / df[population_col]
    return df


def save_dataset_with_metadata(
    df: pd.DataFrame,
    output_dir: Path | str,
    metadata: dict[str, Any],
    filename: str = "output_dataset",
) -> tuple[Path, Path]:
    """Save dataset as CSV and metadata as JSON.

    Returns (csv_path, meta_path).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / f"{filename}.csv"
    meta_path = output_dir / f"{filename}_metadata.json"

    df.to_csv(csv_path, index=False, encoding="utf-8")

    meta = {
        **metadata,
        "rows": len(df),
        "columns": list(df.columns),
        "saved_at": date.today().isoformat(),
    }
    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2, default=str)

    return csv_path, meta_path
