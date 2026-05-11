from __future__ import annotations

from typing import Any

from sentence_transformers import CrossEncoder

from src.ml.rag import dataset_to_text


DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

_reranker_cache: dict[str, CrossEncoder] = {}


def _load_reranker(model_name: str = DEFAULT_RERANKER_MODEL) -> CrossEncoder:
    if model_name not in _reranker_cache:
        _reranker_cache[model_name] = CrossEncoder(model_name)
    return _reranker_cache[model_name]


def rerank_datasets(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    top_k: int = 5,
    model_name: str = DEFAULT_RERANKER_MODEL,
) -> list[dict[str, Any]]:
    """Rerank FAISS candidates with a cross-encoder model (deterministic, local).

    Scores are sigmoid-normalised to [0, 1] by sentence_transformers.
    """
    if not candidates:
        return []

    model = _load_reranker(model_name)

    texts = [dataset_to_text(c) for c in candidates]
    pairs = [(query, text) for text in texts]
    scores = model.predict(pairs)

    scored: list[dict[str, Any]] = []
    for candidate, score in zip(candidates, scores):
        item = dict(candidate)
        item["rerank_score"] = float(score)
        item["rerank_reason"] = ""
        scored.append(item)

    scored.sort(key=lambda x: x["rerank_score"], reverse=True)
    return scored[:top_k]
