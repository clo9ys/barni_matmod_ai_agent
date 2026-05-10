"""Unit tests for pipeline stop-logic — no LLM calls, all mocked."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.core.pipeline import NO_DATA_RERANK_THRESHOLD, run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_search(*_args, **_kwargs):
    return [{"id": "ds1", "title": "Dataset 1", "score": 0.9}]


def _fake_rerank_high(query, candidates, *, top_k=5):
    return [{"id": "ds1", "title": "Dataset 1", "rerank_score": 0.95, "rerank_reason": "relevant"}]


def _fake_rerank_low(query, candidates, *, top_k=5):
    """All scores below threshold — simulates no relevant data."""
    return [{"id": "ds1", "title": "Dataset 1", "rerank_score": 0.1, "rerank_reason": "not relevant"}]


def _fake_research_design(*_args, **_kwargs):
    return {"research_questions": [], "required_indicators": [], "derived_metrics": [], "expected_visualizations": []}


def _fake_codegen(*_args, **_kwargs):
    return "# generated code"


# ---------------------------------------------------------------------------
# Stop 1: query_type == "no_data"
# ---------------------------------------------------------------------------

def test_stop_no_data_query_type():
    params = {"query_type": "no_data", "needs_clarification": False, "clarifying_questions": []}
    with (
        patch("src.core.pipeline.is_llm_configured", return_value=True),
        patch("src.core.pipeline.complete_json", return_value=params),
    ):
        result = run("сколько кислорода в луне", use_full_registry=False)

    assert result["status"] == "no_data"
    assert "reason" in result
    assert "datasets" not in result
    assert "code" not in result


# ---------------------------------------------------------------------------
# Stop 2: needs_clarification == True
# ---------------------------------------------------------------------------

def test_stop_needs_clarification():
    params = {
        "query_type": "ambiguous",
        "needs_clarification": True,
        "clarifying_questions": ["Какую страну имеете в виду?", "Какой период?"],
    }
    with (
        patch("src.core.pipeline.is_llm_configured", return_value=True),
        patch("src.core.pipeline.complete_json", return_value=params),
    ):
        result = run("расскажи про торговлю", use_full_registry=False)

    assert result["status"] == "needs_clarification"
    assert len(result["clarifying_questions"]) == 2
    assert "datasets" not in result
    assert "code" not in result


def test_stop_needs_clarification_empty_questions():
    """needs_clarification=True even with no questions — still stops."""
    params = {"query_type": "ambiguous", "needs_clarification": True, "clarifying_questions": []}
    with (
        patch("src.core.pipeline.is_llm_configured", return_value=True),
        patch("src.core.pipeline.complete_json", return_value=params),
    ):
        result = run("данные", use_full_registry=False)

    assert result["status"] == "needs_clarification"
    assert result["clarifying_questions"] == []


# ---------------------------------------------------------------------------
# Stop 3: all rerank scores below threshold
# ---------------------------------------------------------------------------

def test_stop_low_rerank_scores():
    params = {"query_type": "simple", "needs_clarification": False, "indicators": ["x"], "geography": ["RU"], "time_period": {}, "units": []}
    with (
        patch("src.core.pipeline.is_llm_configured", return_value=True),
        patch("src.core.pipeline.complete_json", return_value=params),
        patch("src.core.pipeline.search_datasets", side_effect=_fake_search),
        patch("src.core.pipeline.rerank_datasets", side_effect=_fake_rerank_low),
    ):
        result = run("очень специфичный запрос без данных", use_full_registry=False)

    assert result["status"] == "no_data"
    assert "datasets" in result  # candidates still returned for debugging
    assert "code" not in result
    best = max(d["rerank_score"] for d in result["datasets"])
    assert best < NO_DATA_RERANK_THRESHOLD


# ---------------------------------------------------------------------------
# Happy path: all checks pass → status == "ok"
# ---------------------------------------------------------------------------

def test_happy_path_status_ok():
    params = {"query_type": "simple", "needs_clarification": False, "indicators": ["CPI"], "geography": ["RU"], "time_period": {"start": 2014, "end": 2024}, "units": []}
    call_count = {"n": 0}

    def fake_complete_json(messages, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return params
        return _fake_research_design()

    with (
        patch("src.core.pipeline.is_llm_configured", return_value=True),
        patch("src.core.pipeline.complete_json", side_effect=fake_complete_json),
        patch("src.core.pipeline.search_datasets", side_effect=_fake_search),
        patch("src.core.pipeline.rerank_datasets", side_effect=_fake_rerank_high),
        patch("src.core.pipeline.generate_analysis_code", side_effect=_fake_codegen),
    ):
        result = run("ИПЦ России 2014–2024", use_full_registry=False, generate_code=True)

    assert result["status"] == "ok"
    assert "datasets" in result
    assert "research_design" in result
    assert result["code"] == "# generated code"
