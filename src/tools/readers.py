"""Utility readers for local archive parquet files."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def read_fedstatru_parquet(
    path: str | Path,
    okato: str = "643",
    period: str = "62",
    years: list[int] | None = None,
) -> pd.DataFrame:
    """Read a Fedstat/Rosstat parquet, handling both named and legacy column formats.

    Named format: columns are real dimension names + year strings ('2017', '2018' ...).
    Legacy format: columns are 'column0'/'column00' etc., row 0 is a header with year floats.

    Returns DataFrame with columns: year (int), value (float).
    Filters by okato (default '643' = Russia) and period (default '62' = December).
    """
    df_raw = pd.read_parquet(path)
    if df_raw.empty:
        return pd.DataFrame(columns=["year", "value"])

    # Detect named format by presence of digit-string column names (e.g. '2017')
    yr_str_cols = [c for c in df_raw.columns if isinstance(c, str) and c.isdigit()]

    if yr_str_cols:
        # Named format: dimension columns already have readable names
        okato_col = next(
            (c for c in df_raw.columns if "ОКАТО" in str(c) or "okato" in str(c).lower()),
            df_raw.columns[1],
        )
        period_col = next(
            (c for c in df_raw.columns if "Период" in str(c) or "период" in str(c).lower()),
            df_raw.columns[3],
        )
        mask = (
            df_raw[okato_col].astype(str).str.contains(okato, na=False)
            & df_raw[period_col].astype(str).str.contains(period, na=False)
        )
        if not mask.any():
            return pd.DataFrame(columns=["year", "value"])
        row = df_raw[mask].iloc[0]
        records = []
        for col in yr_str_cols:
            yr = int(col)
            if (years is None or yr in years) and pd.notna(row[col]):
                records.append({"year": yr, "value": float(row[col])})
        return pd.DataFrame(records)

    else:
        # Legacy format: row 0 is a header row with float year values
        hdr = df_raw.iloc[0]
        yr_cols: dict[Any, int] = {}
        for col in df_raw.columns:
            v = hdr[col]
            if pd.notna(v):
                try:
                    yr = int(float(v))
                    if 1900 <= yr <= 2100:
                        yr_cols[col] = yr
                except (ValueError, TypeError):
                    pass

        df_data = df_raw.iloc[1:].copy()

        # Find okato and period columns by scanning for matching values
        okato_col = next(
            (c for c in df_data.columns if df_data[c].astype(str).str.contains(okato, na=False).any()),
            None,
        )
        period_col = next(
            (
                c for c in df_data.columns
                if df_data[c].astype(str).str.contains(rf"^{period}[ \t]", na=False).any()
                or df_data[c].astype(str).str.fullmatch(period, na=False).any()
            ),
            None,
        )
        # Fallback: period_col = first column (after okato) whose data contains the code
        if period_col is None:
            period_col = next(
                (c for c in df_data.columns if df_data[c].astype(str).str.contains(period, na=False).any()),
                None,
            )

        if okato_col is None or period_col is None:
            return pd.DataFrame(columns=["year", "value"])

        mask = (
            df_data[okato_col].astype(str).str.contains(okato, na=False)
            & df_data[period_col].astype(str).str.contains(period, na=False)
        )
        if not mask.any():
            return pd.DataFrame(columns=["year", "value"])
        row = df_data[mask].iloc[0]
        records = []
        for col, yr in yr_cols.items():
            if (years is None or yr in years) and pd.notna(row[col]):
                records.append({"year": yr, "value": float(row[col])})
        return pd.DataFrame(records)


def read_fedstatru_coverage(
    path: str | Path,
    okato: str = "643",
) -> dict[str, list[int]]:
    """Return {period_label: [years_with_data]} for a Fedstat parquet filtered by OKATO.

    Example: {"62 декабрь": [2018..2024], "118 январь-декабрь": [2018..2024]}
    Allows the assembly plan to pick the right period and set correct years_used.
    """
    try:
        df_raw = pd.read_parquet(path)
        if df_raw.empty:
            return {}

        yr_str_cols = [c for c in df_raw.columns if isinstance(c, str) and c.isdigit()]

        if yr_str_cols:
            okato_col = next(
                (c for c in df_raw.columns if "ОКАТО" in str(c) or "okato" in str(c).lower()),
                df_raw.columns[1],
            )
            period_col = next(
                (c for c in df_raw.columns if "Период" in str(c) or "период" in str(c).lower()),
                df_raw.columns[3],
            )
            mask = df_raw[okato_col].astype(str).str.contains(okato, na=False)
            result: dict[str, list[int]] = {}
            for _, row in df_raw[mask].iterrows():
                label = str(row[period_col])
                result[label] = sorted(int(c) for c in yr_str_cols if pd.notna(row[c]))
            return result
        else:
            hdr = df_raw.iloc[0]
            yr_cols: dict[Any, int] = {}
            for col in df_raw.columns:
                v = hdr[col]
                if pd.notna(v):
                    try:
                        yr = int(float(v))
                        if 1900 <= yr <= 2100:
                            yr_cols[col] = yr
                    except (ValueError, TypeError):
                        pass

            df_data = df_raw.iloc[1:].copy()
            okato_col = next(
                (c for c in df_data.columns if df_data[c].astype(str).str.contains(okato, na=False).any()),
                None,
            )
            if okato_col is None:
                return {}
            cols = list(df_data.columns)
            idx = cols.index(okato_col)
            if idx + 1 >= len(cols):
                return {}
            period_col = cols[idx + 1]
            mask = df_data[okato_col].astype(str).str.contains(okato, na=False)
            result = {}
            for _, row in df_data[mask].iterrows():
                label = str(row[period_col])
                result[label] = sorted(yr for col, yr in yr_cols.items() if pd.notna(row[col]))
            return result
    except Exception:
        return {}


def read_fedstatru_periods(path: str | Path, okato: str = "643") -> list[str]:
    """Return distinct period codes present in a Fedstat parquet for the given OKATO."""
    try:
        df_raw = pd.read_parquet(path)
        if df_raw.empty:
            return []
        yr_str_cols = [c for c in df_raw.columns if isinstance(c, str) and c.isdigit()]
        if yr_str_cols:
            okato_col = next(
                (c for c in df_raw.columns if "ОКАТО" in str(c) or "okato" in str(c).lower()),
                df_raw.columns[1],
            )
            period_col = next(
                (c for c in df_raw.columns if "Период" in str(c) or "период" in str(c).lower()),
                df_raw.columns[3],
            )
            mask = df_raw[okato_col].astype(str).str.contains(okato, na=False)
            return sorted(df_raw.loc[mask, period_col].astype(str).unique().tolist())
        else:
            df_data = df_raw.iloc[1:].copy()
            okato_col = next(
                (c for c in df_data.columns if df_data[c].astype(str).str.contains(okato, na=False).any()),
                None,
            )
            if okato_col is None:
                return []
            cols = list(df_data.columns)
            idx = cols.index(okato_col)
            if idx + 1 >= len(cols):
                return []
            period_col = cols[idx + 1]
            mask = df_data[okato_col].astype(str).str.contains(okato, na=False)
            return sorted(df_data.loc[mask, period_col].astype(str).unique().tolist())
    except Exception:
        return []


def read_wb_parquet(
    path: str | Path,
    countryiso3: str | None = "RUS",
    years: list[int] | None = None,
) -> pd.DataFrame:
    """Read a World Bank long-format parquet file.

    When countryiso3 is a string (e.g. 'RUS'), filters to that country and
    returns columns: year (int), value (float).

    When countryiso3 is None, returns all countries with columns:
    country (ISO3 str), year (int), value (float).
    """
    df = pd.read_parquet(path)
    if countryiso3 is not None:
        df = df[df["countryiso3code"] == countryiso3].copy()
    else:
        df = df.copy()
    df["year"] = pd.to_numeric(df["date"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["year", "value"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    if years:
        df = df[df["year"].isin(years)]
    if countryiso3 is None:
        df = df.rename(columns={"countryiso3code": "country"})
        return df[["country", "year", "value"]].reset_index(drop=True)
    return df[["year", "value"]].reset_index(drop=True)
