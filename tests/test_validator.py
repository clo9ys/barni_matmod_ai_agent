"""Unit tests for assembly plan validator — no real disk access, all mocked."""
from __future__ import annotations

import pathlib
from unittest.mock import patch

import pandas as pd
import pytest

from src.tools.validator import validate_assembly_plan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _source(
    dataset_id="ds1",
    file_path="fedstatru/data/parquet/62685.parquet",
    source_id="fedstatru",
    filters=None,
    years_used=None,
):
    return {
        "dataset_id": dataset_id,
        "file_path": file_path,
        "source_id": source_id,
        "filters": filters or {"okato": "643", "period": "62"},
        "years_used": years_used or [2020, 2021],
    }


def _plan(*sources):
    return {"primary_sources": list(sources)}


# ---------------------------------------------------------------------------
# Check 1: file_path missing
# ---------------------------------------------------------------------------

def test_missing_file_path():
    src = _source(file_path=None)
    errors = validate_assembly_plan(_plan(src), archive_root="/data")
    assert len(errors) == 1
    assert "file_path отсутствует" in errors[0]


# ---------------------------------------------------------------------------
# Check 2: file not found on disk
# ---------------------------------------------------------------------------

def test_file_not_found():
    src = _source()
    # Path.exists() returns False → file not found
    with patch.object(pathlib.Path, "exists", return_value=False):
        errors = validate_assembly_plan(_plan(src), archive_root="/data")
    assert len(errors) == 1
    assert "файл не найден" in errors[0]


# ---------------------------------------------------------------------------
# Check 3: Fedstat — period filter matches nothing (the period='30' bug)
# ---------------------------------------------------------------------------

def test_fedstat_empty_dataframe_shows_available_periods():
    src = _source(filters={"okato": "643", "period": "30"})
    empty_df = pd.DataFrame(columns=["year", "value"])
    with (
        patch.object(pathlib.Path, "exists", return_value=True),
        patch("src.tools.validator.read_fedstatru_parquet", return_value=empty_df),
        patch("src.tools.validator.read_fedstatru_periods", return_value=["62", "118", "1558883"]),
    ):
        errors = validate_assembly_plan(_plan(src), archive_root="/data")

    assert len(errors) == 1
    assert "нет строк" in errors[0]
    assert "period='30'" in errors[0]
    assert "62" in errors[0]  # показывает доступные периоды


# ---------------------------------------------------------------------------
# Check 3: Fedstat — years partially missing
# ---------------------------------------------------------------------------

def test_fedstat_missing_years():
    src = _source(years_used=[2020, 2021, 2024])
    df = pd.DataFrame({"year": [2020, 2021], "value": [4.9, 8.4]})
    with (
        patch.object(pathlib.Path, "exists", return_value=True),
        patch("src.tools.validator.read_fedstatru_parquet", return_value=df),
    ):
        errors = validate_assembly_plan(_plan(src), archive_root="/data")

    assert len(errors) == 1
    assert "2024" in errors[0]
    assert "отсутствуют" in errors[0]


# ---------------------------------------------------------------------------
# Check 3: WB — country not found
# ---------------------------------------------------------------------------

def test_wb_empty_dataframe():
    src = _source(
        file_path="wb/parquet/FP.CPI.TOTL.ZG.parquet",
        source_id="wb",
        filters={"countryiso3": "ZZZ"},
    )
    empty_df = pd.DataFrame(columns=["year", "value"])
    with (
        patch.object(pathlib.Path, "exists", return_value=True),
        patch("src.tools.validator.read_wb_parquet", return_value=empty_df),
    ):
        errors = validate_assembly_plan(_plan(src), archive_root="/data")

    assert len(errors) == 1
    assert "countryiso3='ZZZ'" in errors[0]


# ---------------------------------------------------------------------------
# Happy path: valid plan — no errors
# ---------------------------------------------------------------------------

def test_valid_fedstat_plan():
    src = _source(years_used=[2020, 2021])
    df = pd.DataFrame({"year": [2020, 2021], "value": [4.9, 8.4]})
    with (
        patch.object(pathlib.Path, "exists", return_value=True),
        patch("src.tools.validator.read_fedstatru_parquet", return_value=df),
    ):
        errors = validate_assembly_plan(_plan(src), archive_root="/data")

    assert errors == []


def test_valid_wb_plan():
    src = _source(
        file_path="wb/parquet/FP.CPI.TOTL.ZG.parquet",
        source_id="wb",
        filters={"countryiso3": "RUS"},
        years_used=[2020, 2021],
    )
    df = pd.DataFrame({"year": [2020, 2021], "value": [3.38, 6.69]})
    with (
        patch.object(pathlib.Path, "exists", return_value=True),
        patch("src.tools.validator.read_wb_parquet", return_value=df),
    ):
        errors = validate_assembly_plan(_plan(src), archive_root="/data")

    assert errors == []


# ---------------------------------------------------------------------------
# Multi-source plan: one good, one bad
# ---------------------------------------------------------------------------

def test_multi_source_one_bad():
    good = _source(dataset_id="good", years_used=[2020])
    bad = _source(dataset_id="bad", file_path=None)

    good_df = pd.DataFrame({"year": [2020], "value": [4.9]})
    with (
        patch.object(pathlib.Path, "exists", return_value=True),
        patch("src.tools.validator.read_fedstatru_parquet", return_value=good_df),
    ):
        errors = validate_assembly_plan(_plan(good, bad), archive_root="/data")

    assert len(errors) == 1
    assert "[bad]" in errors[0]


# ---------------------------------------------------------------------------
# Empty plan — no sources → no errors
# ---------------------------------------------------------------------------

def test_empty_plan():
    errors = validate_assembly_plan({"primary_sources": []}, archive_root="/data")
    assert errors == []


# ---------------------------------------------------------------------------
# No archive_root — validation skipped (handled at pipeline level, but
# validate_assembly_plan with empty root uses CWD, so file won't exist)
# ---------------------------------------------------------------------------

def test_no_archive_root_file_not_found():
    src = _source()
    with patch.object(pathlib.Path, "exists", return_value=False):
        errors = validate_assembly_plan(_plan(src), archive_root="")
    assert any("файл не найден" in e for e in errors)
