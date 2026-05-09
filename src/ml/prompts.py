from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = """
ты ии-ассистент для экономистов и исследователей.

твоя задача — помогать превращать пользовательский запрос в формальное исследование,
подбирать подходящие источники данных и формировать дизайн исследования.

важные правила:
- не придумывай числа, факты и названия датасетов
- если данных не хватает, пиши null или unknown
- если запрос неоднозначный, сформулируй уточняющие вопросы
- отвечай только валидным json без markdown
- не добавляй пояснения вне json
""".strip()


EXTRACT_PARAMS_SCHEMA = {
    "query_type": "simple | comparative | research | derived_metric | ambiguous | no_data",
    "original_query": "string",
    "geography": ["string"],
    "time_period": {
        "start": "integer or null",
        "end": "integer or null",
    },
    "indicators": ["string"],
    "subject_area": "string or null",
    "units": ["string"],
    "filters": {
        "countries": ["string"],
        "regions": ["string"],
        "sectors": ["string"],
        "population_groups": ["string"],
    },
    "needs_clarification": "boolean",
    "clarifying_questions": ["string"],
    "assumptions": ["string"],
    "data_requirements": ["string"],
}


RESEARCH_DESIGN_SCHEMA = {
    "research_questions": ["string"],
    "hypotheses": [
        {
            "hypothesis": "string",
            "rationale": "string",
            "required_indicators": ["string"],
        }
    ],
    "required_indicators": [
        {
            "name": "string",
            "role": "main | control | derived | denominator",
            "unit": "string or null",
            "preferred_source": "string or null",
        }
    ],
    "grouping_methods": ["string"],
    "derived_metrics": [
        {
            "name": "string",
            "formula": "string",
            "description": "string",
        }
    ],
    "target_dataset_structure": {
        "grain": "string",
        "dimensions": [
            {
                "name": "string",
                "type": "string",
                "description": "string",
            }
        ],
        "indicators": [
            {
                "name": "string",
                "type": "string",
                "unit": "string or null",
                "description": "string",
            }
        ],
    },
    "expected_visualizations": ["string"],
    "limitations": ["string"],
    "next_step": "string",
}


def format_json_schema(schema: dict[str, Any]) -> str:
    return json.dumps(schema, ensure_ascii=False, indent=2)


def build_extract_params_messages(user_query: str) -> list[dict[str, str]]:
    user_prompt = f"""
разбери пользовательский запрос и верни формальное описание исследования.

запрос пользователя:
{user_query}

верни json строго по такой схеме:
{format_json_schema(EXTRACT_PARAMS_SCHEMA)}

подсказки:
- query_type = simple, если пользователь просит один показатель
- query_type = comparative, если нужно сравнение стран, регионов, периодов или показателей
- query_type = research, если пользователь спрашивает связь, влияние, зависимость или хочет проверить гипотезу
- query_type = derived_metric, если нужно рассчитать индекс, долю, отношение, показатель на душу населения или поправку на инфляцию
- query_type = ambiguous, если непонятны география, период, показатель или единицы
- query_type = no_data, если в запросе явно спрашивается то, что скорее всего отсутствует в экономических источниках
""".strip()

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def build_research_design_messages(
    user_query: str,
    extracted_params: dict[str, Any],
    datasets: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    datasets = datasets or []

    compact_datasets = []
    for dataset in datasets:
        compact_datasets.append(
            {
                "id": dataset.get("id"),
                "title": dataset.get("title"),
                "source": dataset.get("source"),
                "source_url": dataset.get("source_url"),
                "description": dataset.get("description"),
                "indicators": dataset.get("indicators"),
                "score": dataset.get("score"),
            }
        )

    user_prompt = f"""
сформируй дизайн исследования на основе запроса пользователя,
извлеченных параметров и найденных датасетов.

запрос пользователя:
{user_query}

извлеченные параметры:
{json.dumps(extracted_params, ensure_ascii=False, indent=2)}

найденные датасеты:
{json.dumps(compact_datasets, ensure_ascii=False, indent=2)}

верни json строго по такой схеме:
{format_json_schema(RESEARCH_DESIGN_SCHEMA)}

важно:
- не утверждай, что данные точно есть, если среди найденных датасетов нет подходящего источника
- если датасеты подходят частично, явно напиши ограничения
- гипотезы должны быть проверяемыми через показатели
- структура датасета должна быть пригодна для pandas/excel
- если нужен расчет, добавь формулу в derived_metrics
""".strip()

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]