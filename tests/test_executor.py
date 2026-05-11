import pytest
from pathlib import Path

from src.core.executor import run_script


def _write_script(session_dir: Path, code: str) -> None:
    (session_dir / "generated_script.py").write_text(code, encoding="utf-8")


def test_no_script_returns_error(tmp_path):
    result = run_script(tmp_path)
    assert not result.success
    assert result.returncode == -1
    assert any("не найден" in e for e in result.errors)


def test_successful_script(tmp_path):
    _write_script(tmp_path, f"""
import pandas as pd, json
from pathlib import Path

df = pd.DataFrame({{"year": [2020, 2021], "value": [1.0, 2.0]}})
out = Path(r"{tmp_path}")
df.to_csv(out / "output_dataset.csv", index=False)
meta = {{"rows": len(df), "columns": list(df.columns), "saved_at": "2026-01-01"}}
with open(out / "output_dataset_metadata.json", "w") as f:
    json.dump(meta, f)
print("done")
""")
    result = run_script(tmp_path)
    assert result.success
    assert result.output_csv is not None and result.output_csv.exists()
    assert result.output_meta is not None and result.output_meta.exists()
    assert "done" in result.stdout


def test_failing_script(tmp_path):
    _write_script(tmp_path, "raise RuntimeError('boom')")
    result = run_script(tmp_path)
    assert not result.success
    assert result.returncode != 0
    assert result.errors


def test_timeout(tmp_path):
    _write_script(tmp_path, "import time; time.sleep(999)")
    result = run_script(tmp_path, timeout=1)
    assert not result.success
    assert any("таймаут" in e for e in result.errors)


def test_missing_csv_reported(tmp_path):
    _write_script(tmp_path, "print('no csv written')")
    result = run_script(tmp_path)
    assert result.success
    assert result.output_csv is None
    assert any("output_dataset.csv" in e for e in result.errors)
