from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Curated registry (hand-crafted, 18 datasets)
REGISTRY_PATH = PROJECT_ROOT / "data" / "registry.json"
INDEX_DIR = PROJECT_ROOT / "data" / "index"
FAISS_INDEX_PATH = INDEX_DIR / "faiss.index"
METADATA_PATH = INDEX_DIR / "metadata.json"

# Full registry (auto-extracted from archive via preprocessing)
FULL_REGISTRY_PATH = PROJECT_ROOT / "data" / "registry_full.json"
FULL_INDEX_DIR = PROJECT_ROOT / "data" / "index_full"
FULL_FAISS_INDEX_PATH = FULL_INDEX_DIR / "faiss.index"
FULL_METADATA_PATH = FULL_INDEX_DIR / "metadata.json"

DEFAULT_MODEL_NAME = "intfloat/multilingual-e5-small"


def load_registry(registry_path: Path = REGISTRY_PATH) -> list[dict[str, Any]]:
    if not registry_path.exists():
        raise FileNotFoundError(f"registry not found: {registry_path}")

    with registry_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("registry.json must contain a list of datasets")

    if not data:
        raise ValueError("registry.json is empty")

    return data


def dataset_to_text(dataset: dict[str, Any]) -> str:
    indicators = dataset.get("indicators", [])
    indicator_text = "; ".join(
        f"{item.get('name', '')} {item.get('code', '')} {item.get('unit', '')}"
        for item in indicators
        if isinstance(item, dict)
    )

    time_period = dataset.get("time_period") or {}

    parts = [
        dataset.get("title", ""),
        dataset.get("description", ""),
        f"source: {dataset.get('source', '')}",
        f"geography: {', '.join(dataset.get('geography', []))}",
        f"time period: {time_period.get('start', '')}-{time_period.get('end', '')}",
        f"frequency: {dataset.get('frequency', '')}",
        f"indicators: {indicator_text}",
        f"dimensions: {', '.join(dataset.get('dimensions', []))}",
        f"tags: {', '.join(dataset.get('tags', []))}",
    ]

    return "\n".join(str(part) for part in parts if part)


def load_embedding_model(model_name: str = DEFAULT_MODEL_NAME) -> SentenceTransformer:
    return SentenceTransformer(model_name)


def embed_texts(
    texts: list[str],
    model: SentenceTransformer,
    *,
    is_query: bool = False,
) -> np.ndarray:
    prefix = "query: " if is_query else "passage: "
    prepared_texts = [prefix + text for text in texts]

    embeddings = model.encode(
        prepared_texts,
        convert_to_numpy=True,
        show_progress_bar=False,
        normalize_embeddings=True,
    )

    return embeddings.astype("float32")


def build_index(
    registry_path: Path = REGISTRY_PATH,
    index_path: Path = FAISS_INDEX_PATH,
    metadata_path: Path = METADATA_PATH,
    model_name: str = DEFAULT_MODEL_NAME,
) -> None:
    registry = load_registry(registry_path)
    texts = [dataset_to_text(dataset) for dataset in registry]

    model = load_embedding_model(model_name)
    embeddings = embed_texts(texts, model, is_query=False)

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    index_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_path))

    metadata = []
    for dataset, text in zip(registry, texts):
        metadata.append(
            {
                "id": dataset.get("id"),
                "title": dataset.get("title"),
                "description": dataset.get("description"),
                "source": dataset.get("source"),
                "source_id": dataset.get("source_id"),
                "source_url": dataset.get("source_url"),
                "indicator_code": dataset.get("indicator_code"),
                "file_path": dataset.get("file_path"),
                "format": dataset.get("format"),
                "geography": dataset.get("geography"),
                "time_period": dataset.get("time_period"),
                "frequency": dataset.get("frequency"),
                "unit": dataset.get("unit"),
                "indicators": dataset.get("indicators"),
                "dimensions": dataset.get("dimensions"),
                "availability": dataset.get("availability"),
                "tags": dataset.get("tags"),
                "text_for_embedding": text,
            }
        )

    with metadata_path.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)

    print(f"built index for {len(metadata)} datasets")
    print(f"faiss index: {index_path}")
    print(f"metadata: {metadata_path}")


def load_index(
    index_path: Path = FAISS_INDEX_PATH,
    metadata_path: Path = METADATA_PATH,
) -> tuple[faiss.Index, list[dict[str, Any]]]:
    if not index_path.exists() or not metadata_path.exists():
        raise FileNotFoundError("index files not found. run: python -m src.ml.rag build")

    index = faiss.read_index(str(index_path))

    with metadata_path.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    return index, metadata


def search_datasets(
    query: str,
    top_k: int = 5,
    model_name: str = DEFAULT_MODEL_NAME,
    index_path: Path = FAISS_INDEX_PATH,
    metadata_path: Path = METADATA_PATH,
) -> list[dict[str, Any]]:
    if not query.strip():
        raise ValueError("query must not be empty")

    index, metadata = load_index(index_path, metadata_path)
    model = load_embedding_model(model_name)

    query_embedding = embed_texts([query], model, is_query=True)
    scores, indices = index.search(query_embedding, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue

        item = dict(metadata[idx])
        item["score"] = float(score)
        results.append(item)

    return results


def print_results(results: list[dict[str, Any]]) -> None:
    if not results:
        print("no datasets found")
        return

    for number, item in enumerate(results, start=1):
        print(f"\n{number}. {item.get('title')}")
        print(f"   id: {item.get('id')}")
        print(f"   source: {item.get('source')}")
        print(f"   score: {item.get('score'):.4f}")
        print(f"   url: {item.get('source_url')}")
        print(f"   description: {item.get('description')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="build and search dataset registry index")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="build faiss index")
    build_parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    build_parser.add_argument("--registry", default=str(REGISTRY_PATH), help="path to registry JSON")
    build_parser.add_argument("--index-dir", default=str(INDEX_DIR), help="output directory for index files")

    search_parser = subparsers.add_parser("search", help="search datasets")
    search_parser.add_argument("query")
    search_parser.add_argument("--top-k", type=int, default=5)
    search_parser.add_argument("--model", default=DEFAULT_MODEL_NAME)
    search_parser.add_argument("--index-dir", default=str(INDEX_DIR), help="index directory to search in")

    args = parser.parse_args()

    if args.command == "build":
        index_dir = Path(args.index_dir)
        build_index(
            registry_path=Path(args.registry),
            index_path=index_dir / "faiss.index",
            metadata_path=index_dir / "metadata.json",
            model_name=args.model,
        )

    if args.command == "search":
        index_dir = Path(args.index_dir)
        results = search_datasets(
            args.query,
            top_k=args.top_k,
            model_name=args.model,
            index_path=index_dir / "faiss.index",
            metadata_path=index_dir / "metadata.json",
        )
        print_results(results)


if __name__ == "__main__":
    main()