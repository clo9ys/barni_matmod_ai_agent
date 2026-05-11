"""Execute a generated analysis script in a subprocess and return results."""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_TIMEOUT = 120  # seconds


@dataclass
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    returncode: int
    output_csv: Path | None = None
    output_meta: Path | None = None
    errors: list[str] = field(default_factory=list)


def run_script(
    session_dir: Path | str,
    timeout: int = DEFAULT_TIMEOUT,
) -> ExecutionResult:
    """Run generated_script.py from session_dir in a subprocess.

    Returns ExecutionResult with stdout/stderr and paths to output files.
    Looks for output_dataset.csv written by save_dataset_with_metadata.
    """
    session_dir = Path(session_dir)
    script_path = session_dir / "generated_script.py"

    if not script_path.exists():
        return ExecutionResult(
            success=False,
            stdout="",
            stderr="",
            returncode=-1,
            errors=[f"generated_script.py не найден в {session_dir}"],
        )

    project_root = str(session_dir.parent.parent)
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root
    env["MPLBACKEND"] = "Agg"  # non-interactive backend, no GUI window

    try:
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=project_root,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr="",
            returncode=-1,
            errors=[f"Скрипт превысил таймаут {timeout}с"],
        )
    except Exception as exc:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr="",
            returncode=-1,
            errors=[f"Ошибка запуска: {exc}"],
        )

    result = ExecutionResult(
        success=proc.returncode == 0,
        stdout=proc.stdout,
        stderr=proc.stderr,
        returncode=proc.returncode,
    )

    if proc.returncode != 0:
        result.errors.append(
            f"Скрипт завершился с кодом {proc.returncode}.\n{proc.stderr[:2000]}"
        )
        return result

    # Locate output files written by save_dataset_with_metadata
    csv_path = session_dir / "output_dataset.csv"
    meta_path = session_dir / "output_dataset_metadata.json"

    if csv_path.exists():
        result.output_csv = csv_path
    else:
        result.errors.append("output_dataset.csv не создан скриптом")

    if meta_path.exists():
        result.output_meta = meta_path

    return result
