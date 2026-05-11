import json
import pytest
import pandas as pd

from src.tools.skills import (
    rename_value_column,
    filter_years,
    join_on_year,
    join_on_country_year,
    calculate_index_to_base,
    calculate_per_capita,
    save_dataset_with_metadata,
)


def _df(years, values, **extra_cols):
    data = {"year": years, "value": values, **extra_cols}
    return pd.DataFrame(data)


# --- rename_value_column ---

def test_rename_value_column_renames():
    df = _df([2020, 2021], [1.0, 2.0])
    out = rename_value_column(df, "gdp")
    assert "gdp" in out.columns
    assert "value" not in out.columns


def test_rename_value_column_does_not_mutate():
    df = _df([2020], [1.0])
    rename_value_column(df, "x")
    assert "value" in df.columns


# --- filter_years ---

def test_filter_years_keeps_only_requested():
    df = _df([2018, 2019, 2020, 2021], [1, 2, 3, 4])
    out = filter_years(df, [2019, 2021])
    assert list(out["year"]) == [2019, 2021]


def test_filter_years_empty_result():
    df = _df([2018, 2019], [1, 2])
    out = filter_years(df, [2025])
    assert len(out) == 0


# --- join_on_year ---

def test_join_on_year_outer():
    df1 = _df([2019, 2020], [10, 20])
    df2 = _df([2020, 2021], [200, 300])
    df1 = rename_value_column(df1, "a")
    df2 = rename_value_column(df2, "b")
    out = join_on_year(df1, df2, how="outer")
    assert set(out["year"]) == {2019, 2020, 2021}
    assert "a" in out.columns and "b" in out.columns


def test_join_on_year_single_df():
    df = _df([2020], [1.0])
    out = join_on_year(df)
    assert list(out["year"]) == [2020]


def test_join_on_year_empty():
    out = join_on_year()
    assert len(out) == 0


# --- join_on_country_year ---

def test_join_on_country_year_merges():
    df1 = pd.DataFrame({"country": ["RUS", "USA"], "year": [2020, 2020], "a": [1.0, 2.0]})
    df2 = pd.DataFrame({"country": ["RUS", "USA"], "year": [2020, 2020], "b": [10.0, 20.0]})
    out = join_on_country_year(df1, df2)
    assert "a" in out.columns and "b" in out.columns
    assert len(out) == 2


# --- calculate_index_to_base ---

def test_calculate_index_to_base_base_is_100():
    df = _df([2015, 2016, 2017], [50.0, 60.0, 75.0])
    out = calculate_index_to_base(df, base_year=2015)
    base_row = out[out["year"] == 2015]
    assert abs(base_row["value_index_2015"].iloc[0] - 100.0) < 1e-9


def test_calculate_index_to_base_ratio():
    df = _df([2015, 2016], [50.0, 100.0])
    out = calculate_index_to_base(df, base_year=2015)
    assert abs(out[out["year"] == 2016]["value_index_2015"].iloc[0] - 200.0) < 1e-9


def test_calculate_index_to_base_missing_year():
    df = _df([2016, 2017], [1.0, 2.0])
    with pytest.raises(ValueError, match="base_year=2015 not found"):
        calculate_index_to_base(df, base_year=2015)


def test_calculate_index_to_base_zero_base():
    df = _df([2015, 2016], [0.0, 10.0])
    with pytest.raises(ValueError, match="base value.*is zero"):
        calculate_index_to_base(df, base_year=2015)


def test_calculate_index_to_base_custom_col():
    df = _df([2020, 2021], [100.0, 150.0])
    out = calculate_index_to_base(df, base_year=2020, index_col="idx")
    assert "idx" in out.columns


# --- calculate_per_capita ---

def test_calculate_per_capita_divides():
    df = pd.DataFrame({"year": [2020], "gdp": [1000.0], "pop": [10.0]})
    out = calculate_per_capita(df, "gdp", "pop")
    assert abs(out["gdp_per_capita"].iloc[0] - 100.0) < 1e-9


def test_calculate_per_capita_custom_result_col():
    df = pd.DataFrame({"year": [2020], "gdp": [500.0], "pop": [5.0]})
    out = calculate_per_capita(df, "gdp", "pop", result_col="gdp_pc")
    assert "gdp_pc" in out.columns


# --- save_dataset_with_metadata ---

def test_save_dataset_with_metadata_files_created(tmp_path):
    df = _df([2020, 2021], [1.0, 2.0])
    csv_path, meta_path = save_dataset_with_metadata(
        df, tmp_path, metadata={"query": "test"}, filename="out"
    )
    assert csv_path.exists()
    assert meta_path.exists()


def test_save_dataset_with_metadata_content(tmp_path):
    df = _df([2020], [42.0])
    csv_path, meta_path = save_dataset_with_metadata(
        df, tmp_path, metadata={"query": "q"}, filename="result"
    )
    loaded = pd.read_csv(csv_path)
    assert list(loaded["year"]) == [2020]

    with meta_path.open() as f:
        meta = json.load(f)
    assert meta["query"] == "q"
    assert meta["rows"] == 1
    assert "year" in meta["columns"]


def test_save_dataset_with_metadata_creates_dir(tmp_path):
    df = _df([2020], [1.0])
    new_dir = tmp_path / "nested" / "dir"
    save_dataset_with_metadata(df, new_dir, metadata={}, filename="x")
    assert new_dir.exists()
