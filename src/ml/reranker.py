from __future__ import annotations

from typing import Any

from src.ml.model import complete_json
from src.ml.prompts import build_rerank_messages


def rerank_datasets(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Rerank FAISS candidates using YandexGPT as a pointwise relevance judge.

    Each candidate is scored independently (0.0–1.0). Falls back to the
    original FAISS score if the LLM call fails.
    """
    if not candidates:
        return []

    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        item = dict(candidate)
        try:
            messages = build_rerank_messages(query, candidate)
            result = complete_json(messages, temperature=0.0, max_tokens=200)
            item["rerank_score"] = float(result.get("score", 0.0))
            item["rerank_reason"] = result.get("reason", "")
        except Exception:
            item["rerank_score"] = float(candidate.get("score", 0.0))
            item["rerank_reason"] = ""
        scored.append(item)

    scored.sort(key=lambda x: x["rerank_score"], reverse=True)
    return scored[:top_k]
