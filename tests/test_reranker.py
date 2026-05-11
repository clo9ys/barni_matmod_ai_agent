"""Tests for CrossEncoder-based reranker (deterministic, no LLM calls)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.ml.reranker import rerank_datasets


def _make_candidates(n: int) -> list[dict]:
    return [
        {
            "id": f"ds_{i}",
            "title": f"Dataset {i}",
            "description": f"description {i}",
            "source": "test",
            "indicators": [],
            "geography": ["Russia"],
            "time_period": {"start": 2015, "end": 2023},
            "tags": [],
            "score": float(i + 1) / n,
        }
        for i in range(n)
    ]


def _mock_reranker(scores: list[float]):
    mock = MagicMock()
    mock.predict.return_value = scores
    return mock


def test_empty_candidates_returns_empty():
    result = rerank_datasets("query", [])
    assert result == []


@patch("src.ml.reranker._load_reranker")
def test_sorted_by_rerank_score(mock_load):
    candidates = _make_candidates(3)
    mock_load.return_value = _mock_reranker([0.1, 0.9, 0.5])

    result = rerank_datasets("query", candidates, top_k=3)

    assert result[0]["id"] == "ds_1"
    assert result[1]["id"] == "ds_2"
    assert result[2]["id"] == "ds_0"


@patch("src.ml.reranker._load_reranker")
def test_top_k_limits_results(mock_load):
    candidates = _make_candidates(5)
    mock_load.return_value = _mock_reranker([0.9, 0.8, 0.7, 0.6, 0.5])

    result = rerank_datasets("query", candidates, top_k=3)

    assert len(result) == 3


@patch("src.ml.reranker._load_reranker")
def test_rerank_score_stored(mock_load):
    candidates = _make_candidates(2)
    mock_load.return_value = _mock_reranker([0.75, 0.25])

    result = rerank_datasets("query", candidates, top_k=2)

    assert abs(result[0]["rerank_score"] - 0.75) < 1e-6
    assert abs(result[1]["rerank_score"] - 0.25) < 1e-6


@patch("src.ml.reranker._load_reranker")
def test_original_fields_preserved(mock_load):
    candidates = _make_candidates(1)
    candidates[0]["geography"] = ["Germany"]
    mock_load.return_value = _mock_reranker([0.5])

    result = rerank_datasets("query", candidates, top_k=1)

    assert result[0]["geography"] == ["Germany"]
    assert result[0]["id"] == "ds_0"


@patch("src.ml.reranker._load_reranker")
def test_deterministic_same_scores(mock_load):
    candidates = _make_candidates(3)
    fixed_scores = [0.8, 0.3, 0.6]
    mock_load.return_value = _mock_reranker(fixed_scores)
    result1 = rerank_datasets("query", candidates, top_k=3)

    mock_load.return_value = _mock_reranker(fixed_scores)
    result2 = rerank_datasets("query", candidates, top_k=3)

    assert [r["id"] for r in result1] == [r["id"] for r in result2]
