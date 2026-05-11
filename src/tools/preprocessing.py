from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".parquet"}

KNOWN_SOURCES: dict[str, str] = {
    "world_bank": "World Bank",
    "rosstat": "Rosstat",
    "wto": "World Trade Organization",
    "unesco": "UNESCO",
    "imf": "IMF",
    "un_comtrade": "UN Comtrade",
    "oecd": "OECD",
    "eurostat": "Eurostat",
    "cbr": "Central Bank of Russia",
    "federal_reserve": "Federal Reserve",
}

_DATE_KW = {"year", "date", "period", "time", "год", "дата", "месяц", "квартал", "quarter", "month"}
_GEO_KW = {"country", "region", "страна", "регион", "geo", "geography", "territory", "oblast", "city", "iso"}
_SKIP_KW = _DATE_KW | _GEO_KW | {"id", "code", "iso", "fips", "nuts", "index", "flag"}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "registry_full.json"


def _detect_source(file_path: Path) -> tuple[str, str]:
    for part in file_path.parts:
        key = part.lower().replace("-", "_").replace(" ", "_")
        if key in KNOWN_SOURCES:
            return key, KNOWN_SOURCES[key]
    return "unknown", "Unknown"


def _read_sample(file_path: Path, nrows: int = 300) -> pd.DataFrame | None:
    ext = file_path.suffix.lower()
    try:
        if ext == ".csv":
            df = pd.read_csv(file_path, nrows=nrows, low_memory=False)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(file_path, nrows=nrows)
        elif ext == ".parquet":
            df = pd.read_parquet(file_path).head(nrows)
        elif ext == ".json":
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                df = pd.DataFrame(data[:nrows])
            elif isinstance(data, dict):
                df = pd.DataFrame.from_dict(data, orient="index").head(nrows)
            else:
                return None
        else:
            return None
        df.columns = df.columns.astype(str)
        return df
    except Exception:
        pass
    return None


def _detect_time_period(df: pd.DataFrame) -> dict[str, int | None]:
    for col in df.columns:
        if any(kw in col.lower() for kw in _DATE_KW):
            try:
                vals = pd.to_numeric(df[col].dropna(), errors="coerce").dropna()
                mn, mx = int(vals.min()), int(vals.max())
                if 1800 <= mn <= 2100 and 1800 <= mx <= 2100:
                    return {"start": mn, "end": mx}
            except Exception:
                continue
    return {"start": None, "end": None}


def _detect_geography(df: pd.DataFrame) -> list[str]:
    for col in df.columns:
        if any(kw in col.lower() for kw in _GEO_KW):
            try:
                return [str(v) for v in df[col].dropna().unique()[:30]]
            except Exception:
                continue
    return []


def _detect_indicators(df: pd.DataFrame) -> list[dict[str, str]]:
    result = []
    for col in df.columns:
        col_lower = col.lower()
        if any(kw in col_lower for kw in _SKIP_KW):
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            result.append({"name": col, "code": col_lower.replace(" ", "_"), "unit": ""})
    return result[:20]


def extract_file_metadata(file_path: Path, archive_root: Path) -> dict[str, Any] | None:
    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return None

    df = _read_sample(file_path)
    if df is None or df.empty:
        return None

    source_id, source_name = _detect_source(file_path)
    relative = file_path.relative_to(archive_root)

    file_id = "_".join(relative.with_suffix("").parts).lower()
    file_id = file_id.replace(" ", "_").replace("-", "_").replace("\\", "_").replace("/", "_")

    title = file_path.stem.replace("_", " ").replace("-", " ").title()

    return {
        "id": file_id,
        "title": title,
        "source": source_name,
        "source_id": source_id,
        "file_path": str(relative).replace("\\", "/"),
        "format": file_path.suffix.lower().lstrip("."),
        "columns": list(df.columns),
        "time_period": _detect_time_period(df),
        "geography": _detect_geography(df),
        "indicators": _detect_indicators(df),
        "description": "",
        "tags": [source_id],
        "dimensions": [],
    }


def scan_archive(
    archive_root: Path,
    output_path: Path = DEFAULT_OUTPUT,
    *,
    verbose: bool = True,
) -> list[dict[str, Any]]:
    archive_root = Path(archive_root).resolve()
    output_path = Path(output_path)

    files = [
        f for f in archive_root.rglob("*")
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if verbose:
        print(f"found {len(files)} files in {archive_root}")

    results: list[dict[str, Any]] = []
    for i, fp in enumerate(files, start=1):
        if verbose:
            print(f"[{i}/{len(files)}] {fp.relative_to(archive_root)}", end=" ... ", flush=True)

        meta = extract_file_metadata(fp, archive_root)
        if meta is not None:
            results.append(meta)
            if verbose:
                print("ok")
        else:
            if verbose:
                print("skipped")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"\nextracted {len(results)} datasets -> {output_path}")

    return results


def enrich_with_llm(
    registry_path: Path,
    output_path: Path | None = None,
    *,
    verbose: bool = True,
) -> list[dict[str, Any]]:
    from src.ml.model import complete_json
    from src.ml.prompts import build_enrich_metadata_messages

    registry_path = Path(registry_path)
    output_path = output_path or registry_path

    with registry_path.open("r", encoding="utf-8") as f:
        metadata_list: list[dict[str, Any]] = json.load(f)

    for i, meta in enumerate(metadata_list, start=1):
        if meta.get("description"):
            continue

        if verbose:
            print(f"[{i}/{len(metadata_list)}] enriching: {meta['title']}", end=" ... ", flush=True)

        try:
            messages = build_enrich_metadata_messages(meta)
            result = complete_json(messages)
            meta["description"] = result.get("description", "")
            meta["tags"] = list({*meta.get("tags", []), *result.get("tags", [])})
            if verbose:
                print("ok")
        except Exception as e:
            if verbose:
                print(f"error: {e}")

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(metadata_list, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"\nenriched {len(metadata_list)} entries -> {output_path}")

    return metadata_list


# ---------------------------------------------------------------------------
# Specialized builder for the wb + fedstatru archive structure
# ---------------------------------------------------------------------------

def _wb_metatype_value(metatypes: list[dict], key: str) -> str:
    for m in metatypes:
        if m.get("id") == key:
            v = m.get("value", "")
            return str(v).strip() if v else ""
    return ""


def _build_wb_registry(archive_root: Path) -> list[dict[str, Any]]:
    """Build registry entries from wb/metadata/*.json using parquet paths as file refs."""
    meta_dir = archive_root / "wb" / "metadata"
    parquet_dir = archive_root / "wb" / "parquet"

    if not meta_dir.exists():
        return []

    # Build set of available parquet files for fast lookup
    available_parquet = {p.stem for p in parquet_dir.glob("*.parquet")} if parquet_dir.exists() else set()

    seen_ids: set[str] = set()
    entries: list[dict[str, Any]] = []
    for meta_file in sorted(meta_dir.glob("*.json")):
        try:
            with meta_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        if not isinstance(data, list):
            continue

        for item in data:
            indicator_id: str = item.get("id", "")
            if not indicator_id or indicator_id in seen_ids:
                continue
            seen_ids.add(indicator_id)

            metatypes: list[dict] = item.get("metatype", [])
            title = _wb_metatype_value(metatypes, "IndicatorName") or indicator_id
            description = (
                _wb_metatype_value(metatypes, "Longdefinition")
                or _wb_metatype_value(metatypes, "ShortDefinition")
            )
            frequency = _wb_metatype_value(metatypes, "Periodicity")
            source_note = _wb_metatype_value(metatypes, "Source")

            file_path = f"wb/parquet/{indicator_id}.parquet" if indicator_id in available_parquet else None

            entry: dict[str, Any] = {
                "id": f"wb_{indicator_id.replace('.', '_').lower()}",
                "title": title,
                "source": "World Bank",
                "source_id": "wb",
                "source_url": f"https://data.worldbank.org/indicator/{indicator_id}",
                "indicator_code": indicator_id,
                "file_path": file_path,
                "format": "parquet",
                "description": description,
                "frequency": frequency,
                "source_note": source_note,
                "geography": ["world", "countries"],
                "time_period": {"start": None, "end": None},
                "indicators": [{"name": title, "code": indicator_id, "unit": ""}],
                "dimensions": ["country", "year"],
                "tags": ["world bank", indicator_id.lower()],
            }
            entries.append(entry)

    return entries


def _build_fedstatru_registry(archive_root: Path) -> list[dict[str, Any]]:
    """Build registry entries from fedstatru/data/metadata/*.json."""
    meta_dir = archive_root / "fedstatru" / "data" / "metadata"
    parquet_dir = archive_root / "fedstatru" / "data" / "parquet"

    if not meta_dir.exists():
        return []

    available_parquet = {p.stem for p in parquet_dir.glob("*.parquet")} if parquet_dir.exists() else set()

    # Known Russian prop keys mapped to registry fields
    KEY_TIME_RANGE = "Диапазон временных рядов"
    KEY_UNIT = "Единицы измерения"
    KEY_FREQUENCY = "Периодичность"
    KEY_RESPONSIBLE = "Ответственный"

    entries: list[dict[str, Any]] = []
    for meta_file in sorted(meta_dir.glob("*.json")):
        try:
            with meta_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        code = str(data.get("code", meta_file.stem))
        name: str = data.get("name", "") or ""
        props: dict = data.get("props", {})

        time_range_raw: str = props.get(KEY_TIME_RANGE, "")
        unit: str = props.get(KEY_UNIT, "")
        frequency: str = props.get(KEY_FREQUENCY, "")
        responsible: str = props.get(KEY_RESPONSIBLE, "")

        # Parse time range "2000 - 2025"
        time_period: dict[str, int | None] = {"start": None, "end": None}
        if " - " in time_range_raw:
            parts = time_range_raw.split(" - ")
            try:
                time_period["start"] = int(parts[0].strip())
                time_period["end"] = int(parts[1].strip())
            except ValueError:
                pass

        file_path = f"fedstatru/data/parquet/{code}.parquet" if code in available_parquet else None

        entry: dict[str, Any] = {
            "id": f"fedstatru_{code}",
            "title": name or f"Fedstat indicator {code}",
            "source": "Rosstat / Fedstat",
            "source_id": "fedstatru",
            "source_url": f"https://fedstat.ru/indicator/{code}",
            "indicator_code": code,
            "file_path": file_path,
            "format": "parquet",
            "description": name,
            "frequency": frequency,
            "unit": unit,
            "responsible": responsible,
            "geography": ["Russia", "Russian regions"],
            "time_period": time_period,
            "indicators": [{"name": name, "code": code, "unit": unit}],
            "dimensions": [],
            "tags": ["росстат", "россия", "fedstat", code],
        }
        entries.append(entry)

    return entries


def build_registry_from_archive(
    archive_root: Path,
    output_path: Path = DEFAULT_OUTPUT,
    *,
    verbose: bool = True,
) -> list[dict[str, Any]]:
    """Build a rich registry from wb + fedstatru metadata files (no LLM needed)."""
    archive_root = Path(archive_root).resolve()

    if verbose:
        print("Building registry from existing metadata files...")

    wb_entries = _build_wb_registry(archive_root)
    if verbose:
        print(f"  World Bank: {len(wb_entries)} indicators")

    fed_entries = _build_fedstatru_registry(archive_root)
    if verbose:
        print(f"  Fedstat:    {len(fed_entries)} indicators")

    all_entries = wb_entries + fed_entries

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"Total: {len(all_entries)} entries -> {output_path}")

    return all_entries


def main() -> None:
    parser = argparse.ArgumentParser(description="preprocess archive into metadata registry")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_p = subparsers.add_parser("build", help="build registry from wb+fedstatru metadata (recommended)")
    build_p.add_argument("archive", help="path to archive root (e.g. D:\\data)")
    build_p.add_argument("--output", default=str(DEFAULT_OUTPUT))

    scan_p = subparsers.add_parser("scan", help="generic scan of any archive directory")
    scan_p.add_argument("archive", help="path to archive root directory")
    scan_p.add_argument("--output", default=str(DEFAULT_OUTPUT))

    enrich_p = subparsers.add_parser("enrich", help="enrich metadata with LLM descriptions")
    enrich_p.add_argument("--registry", default=str(DEFAULT_OUTPUT))
    enrich_p.add_argument("--output", default=None)

    args = parser.parse_args()

    if args.command == "build":
        build_registry_from_archive(Path(args.archive), Path(args.output))

    if args.command == "scan":
        scan_archive(Path(args.archive), Path(args.output))

    if args.command == "enrich":
        out = Path(args.output) if args.output else None
        enrich_with_llm(Path(args.registry), out)


if __name__ == "__main__":
    main()
