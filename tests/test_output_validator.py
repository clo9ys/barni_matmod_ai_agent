import json
import pandas as pd
import pytest
from pathlib import Path

from src.tools.output_validator import validate_output_dataset, output_validation_summary


def _write_csv(path: Path, df: pd.DataFrame) -> None:
    df.to_csv(path, index=False)


def test_file_not_found(tmp_path):
    errors = validate_output_dataset(tmp_path / "missing.csv")
    assert any("не найден" in e for e in errors)


def test_unreadable_file(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("not,a,csv\n{{{{")
    # pandas can still read this — just check it doesn't crash
    errors = validate_output_dataset(p)
    assert isinstance(errors, list)


def test_empty_dataframe(tmp_path):
    p = tmp_path / "out.csv"
    pd.DataFrame(columns=["year", "value"]).to_csv(p, index=False)
    errors = validate_output_dataset(p, min_rows=1)
    assert any("мал" in e or "пуст" in e for e in errors)


def test_valid_dataset_no_errors(tmp_path):
    p = tmp_path / "out.csv"
    df = pd.DataFrame({"year": [2020, 2021], "gdp": [1.0, 2.0], "country": ["RUS", "RUS"]})
    _write_csv(p, df)
    errors = validate_output_dataset(p)
    assert errors == []


def test_missing_expected_column(tmp_path):
    p = tmp_path / "out.csv"
    df = pd.DataFrame({"year": [2020], "gdp": [1.0]})
    _write_csv(p, df)
    errors = validate_output_dataset(p, expected_columns=["year", "gdp", "urbanization"])
    assert any("urbanization" in e for e in errors)


def test_all_null_indicator_column(tmp_path):
    p = tmp_path / "out.csv"
    df = pd.DataFrame({"year": [2020, 2021], "gdp": [None, None], "country": ["RUS", "CHN"]})
    _write_csv(p, df)
    errors = validate_output_dataset(p)
    assert any("gdp" in e for e in errors)


def test_metadata_columns_not_flagged_as_empty(tmp_path):
    p = tmp_path / "out.csv"
    df = pd.DataFrame({
        "year": [2020],
        "country": ["RUS"],
        "source": ["wb"],
        "extraction_date": ["2026-01-01"],
        "gdp": [1.5],
    })
    _write_csv(p, df)
    errors = validate_output_dataset(p)
    assert errors == []


def test_output_validation_summary_no_csv():
    result = {"execution": {}, "assembly_plan": {}}
    summary = output_validation_summary(result)
    assert not summary["valid"]
    assert summary["errors"]


def test_output_validation_summary_valid(tmp_path):
    p = tmp_path / "out.csv"
    df = pd.DataFrame({"year": [2020], "country": ["RUS"], "gdp": [1.0]})
    _write_csv(p, df)
    result = {
        "execution": {"output_csv": str(p)},
        "assembly_plan": {"output_columns": [{"name": "year"}, {"name": "country"}, {"name": "gdp"}]},
    }
    summary = output_validation_summary(result)
    assert summary["valid"]
    assert summary["errors"] == []
