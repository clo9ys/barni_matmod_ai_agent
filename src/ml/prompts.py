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
    "english_query": "string — English search phrase using official statistical terminology, NOT colloquial translation. Examples: use 'consumer price index CPI' not 'inflation'; 'gross domestic product GDP' not 'economic growth'; 'unemployment rate' not 'joblessness'; 'gross fixed capital formation' not 'investment'",
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
- english_query: обязательно используй официальные статистические термины на английском, не разговорный перевод:
  инфляция → "consumer price index CPI inflation"
  ВВП/валовый продукт → "gross domestic product GDP"
  безработица → "unemployment rate labor market"
  инвестиции → "gross fixed capital formation investment"
  зарплата → "average wage salary earnings"
  население → "population demographics"
  торговый баланс → "trade balance exports imports"
- query_type = simple, если пользователь просит один показатель
- query_type = comparative, если нужно сравнение стран, регионов, периодов или показателей
- query_type = research, если пользователь спрашивает связь, влияние, зависимость или хочет проверить гипотезу
- query_type = derived_metric, если нужно рассчитать индекс, долю, отношение, показатель на душу населения или поправку на инфляцию
- query_type = ambiguous, если непонятны география, период, показатель или единицы
- query_type = no_data, если в запросе явно спрашивается то, что скорее всего отсутствует в экономических источниках: страны с закрытой экономикой без официальной статистики (КНДР / Северная Корея, Эритрея, Туркменистан и т.п.), секретные военные расходы, данные теневого рынка, неизмеримые социальные феномены и т.д.
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


# ---------------------------------------------------------------------------
# Reranker prompts (batch — one LLM call for all candidates)
# ---------------------------------------------------------------------------

BATCH_RERANK_SYSTEM_PROMPT = """
ты — аналитик данных. для каждого датасета прими бинарное решение: подходит он для ответа на запрос или нет.

правила relevant=1 (датасет подходит) — все три условия должны выполняться:
1. хотя бы один показатель датасета совпадает или близок к запрошенным индикаторам
2. география датасета покрывает хотя бы одну из запрошенных стран/регионов
3. временной период датасета пересекается с запрошенным периодом

правила relevant=0 (датасет не подходит) — достаточно одного:
- показатели датасета не пересекаются с запрошенными
- датасет относится к совсем другой теме
- география или период полностью не совпадают

отвечай только валидным json без markdown:
{"rankings": [{"id": "...", "relevant": 1, "reason": "одно предложение почему"}]}

каждый датасет из списка должен получить оценку.
""".strip()


def build_batch_rerank_messages(
    query: str,
    datasets: list[dict[str, Any]],
) -> list[dict[str, str]]:
    compact = [
        {
            "id": d.get("id"),
            "title": d.get("title"),
            "source": d.get("source"),
            "description": d.get("description"),
            "indicators": d.get("indicators"),
            "geography": d.get("geography"),
            "time_period": d.get("time_period"),
            "tags": d.get("tags"),
        }
        for d in datasets
    ]

    user_prompt = f"""
запрос пользователя: {query}

датасеты для оценки ({len(datasets)} шт.):
{json.dumps(compact, ensure_ascii=False, indent=2)}

для каждого датасета верни relevant=1 или relevant=0 по правилам из системного промпта.
""".strip()

    return [
        {"role": "system", "content": BATCH_RERANK_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


# ---------------------------------------------------------------------------
# Metadata enrichment prompts
# ---------------------------------------------------------------------------

ENRICH_SYSTEM_PROMPT = """
ты — эксперт по экономической статистике.

тебе дают технические метаданные файла: название, источник, колонки, образец данных.
твоя задача — написать понятное описание датасета и подобрать теги для поиска.

отвечай только валидным json без markdown:
{"description": "string", "tags": ["string"]}

правила:
- описание на английском, 2–3 предложения: что за данные и для чего они полезны
- теги: названия показателей, источник, тематика + русские переводы ключевых слов
- не придумывай данные которых нет в метаданных
""".strip()


def build_enrich_metadata_messages(metadata: dict[str, Any]) -> list[dict[str, str]]:
    info = {
        "title": metadata.get("title"),
        "source": metadata.get("source"),
        "file_path": metadata.get("file_path"),
        "columns": (metadata.get("columns") or [])[:30],
        "indicators": (metadata.get("indicators") or [])[:10],
        "time_period": metadata.get("time_period"),
        "geography": (metadata.get("geography") or [])[:10],
    }

    user_prompt = f"""
опиши датасет на основе метаданных:
{json.dumps(info, ensure_ascii=False, indent=2)}
""".strip()

    return [
        {"role": "system", "content": ENRICH_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


# ---------------------------------------------------------------------------
# Assembly plan prompts
# ---------------------------------------------------------------------------

ASSEMBLY_PLAN_SYSTEM_PROMPT = """
ты — аналитик данных. твоя задача — составить план сборки датасета:
решить, какие источники использовать, отвергнуть лишние, и описать,
как объединить данные в целевую структуру.

отвечай только валидным json без markdown.
не придумывай dataset_id или file_path — используй только те, что переданы в запросе.
""".strip()

ASSEMBLY_PLAN_SCHEMA = {
    "primary_sources": [
        {
            "dataset_id": "string — id из реестра",
            "file_path": "string — путь к файлу относительно ARCHIVE_ROOT (из метаданных)",
            "source_id": "string — fedstatru | wb | rosstat | ...",
            "role": "main | supplementary",
            "years_used": ["int — только те годы, которые реально есть в файле"],
            "filters": {
                "okato": "string или null — код ОКАТО (для Fedstat; 643 = Россия)",
                "period": "string или null — код периода; ТОЛЬКО числовая часть ключа из available_coverage (например '62 декабрь' → '62'); НЕ используй период которого нет в available_coverage",
                "countryiso3": "string или null — ISO3 (для WB; RUS = Россия)",
            },
            "reason": "string — почему выбран этот источник",
        }
    ],
    "rejected_sources": [
        {
            "dataset_id": "string",
            "reason": "string — почему отвергнут",
        }
    ],
    "combination_strategy": "single_source | concat_by_year | priority_merge | join",
    "join_key": "year | null",
    "output_columns": [
        {
            "name": "string — итоговое название колонки",
            "source_col": "string — откуда берётся (year / value / ...)",
            "type": "int | float | str | date",
            "unit": "string или null",
        }
    ],
}


def build_assembly_plan_messages(
    user_query: str,
    extracted_params: dict[str, Any],
    top_datasets: list[dict[str, Any]],
    research_design: dict[str, Any],
    validation_errors: list[str] | None = None,
) -> list[dict[str, str]]:
    compact_datasets = [
        {
            "id": d.get("id"),
            "title": d.get("title"),
            "source": d.get("source"),
            "source_id": d.get("source_id"),
            "file_path": d.get("file_path"),
            "format": d.get("format"),
            "time_period": d.get("time_period"),
            "geography": d.get("geography"),
            "available_coverage": d.get("available_coverage"),
            "rerank_score": d.get("rerank_score"),
            "rerank_reason": d.get("rerank_reason"),
        }
        for d in top_datasets
    ]

    retry_block = ""
    if validation_errors:
        errors_str = "\n".join(f"  - {e}" for e in validation_errors)
        retry_block = f"""
ВНИМАНИЕ: предыдущий план провалил валидацию. Исправь следующие ошибки:
{errors_str}

Если датасет не содержит нужных фильтров (okato/period/country) — выбери другой датасет из списка.
Для международных данных (не Россия) предпочитай World Bank (wb) источники с нужным countryiso3.
"""

    user_prompt = f"""
запрос: {user_query}

период исследования: {json.dumps(extracted_params.get("time_period"), ensure_ascii=False)}
география: {json.dumps(extracted_params.get("geography"), ensure_ascii=False)}
нужные индикаторы: {json.dumps(research_design.get("required_indicators", []), ensure_ascii=False, indent=2)}

доступные датасеты (выбирай только из этого списка):
{json.dumps(compact_datasets, ensure_ascii=False, indent=2)}
{retry_block}
составь план сборки по схеме:
{format_json_schema(ASSEMBLY_PLAN_SCHEMA)}

правила:
- в primary_sources включай только датасеты с file_path != null
- если несколько источников покрывают разные периоды — используй combination_strategy = "priority_merge"
- если данные за нужный период есть только в одном источнике — combination_strategy = "single_source"
- years_used — только реальный диапазон из поля time_period датасета, пересечённый с запрошенным периодом
- output_columns — итоговая структура результирующего датасета
- для Fedstat датасетов: available_coverage — словарь {{"период-метка": [годы с данными]}}
  - filters.period ОБЯЗАН быть числовой частью ключа из available_coverage
    (например "62 декабрь" → period="62", "118 январь-декабрь" → period="118")
  - НЕ используй period которого нет в available_coverage
  - years_used = пересечение запрошенного периода и лет из available_coverage[выбранный период]
- если один датасет не покрывает все запрошенные годы: используй combination_strategy="priority_merge"
  и добавь supplementary источник из другого датасета для непокрытых лет,
  у каждого источника years_used должен содержать только реально доступные годы из его available_coverage
""".strip()

    return [
        {"role": "system", "content": ASSEMBLY_PLAN_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


# ---------------------------------------------------------------------------
# Code generation prompts
# ---------------------------------------------------------------------------

CODEGEN_SYSTEM_PROMPT = """
ты — python-разработчик специализирующийся на экономических данных.

напиши готовый к запуску python-скрипт который:
1. загружает данные из локального архива parquet-файлов (путь будет передан в промпте)
2. объединяет данные из нескольких источников в один pandas dataframe
3. рассчитывает производные метрики
4. строит графики
5. сохраняет итоговый датасет в OUTPUT_DIR

правила кода:
- только рабочий python-код без пояснений вне кода
- используй: pandas, numpy, matplotlib, pathlib, datetime
- не используй requests и не обращайся к внешним api — только локальные файлы
- полный путь к файлу: Path(ARCHIVE_ROOT) / file_path  (file_path из метаданных датасета)
- НЕ используй plt.show() — скрипт запускается headless, GUI недоступен
- каждый график сохраняй через plt.savefig(OUTPUT_DIR / "plot_N.png", dpi=100, bbox_inches="tight"); plt.close()
- при использовании plt.xticks() всегда приводи year к int: plt.xticks(final_df["year"].astype(int))

== загрузка данных — используй готовые утилиты из src.tools.readers ==

для Fedstat / Rosstat (fedstatru/data/parquet/*.parquet):
  from src.tools.readers import read_fedstatru_parquet
  df = read_fedstatru_parquet(
      path=Path(ARCHIVE_ROOT) / file_path,
      okato='643',    # 643 = Россия (или код региона)
      period='62',    # 62 = декабрь; 30 = год в целом; 118 = январь-декабрь
      years=[2014, 2015, ..., 2024],  # или None для всех лет
  )
  # возвращает DataFrame с колонками: year (int), value (float)

для World Bank (wb/parquet/*.parquet):
  from src.tools.readers import read_wb_parquet
  # одна страна:
  df = read_wb_parquet(
      path=Path(ARCHIVE_ROOT) / file_path,
      countryiso3='RUS',    # iso3 код страны
      years=[2014, ..., 2024],
  )
  # возвращает DataFrame с колонками: year (int), value (float)

  # все страны (панельные данные):
  df = read_wb_parquet(
      path=Path(ARCHIVE_ROOT) / file_path,
      countryiso3=None,     # None = все страны
      years=[2014, ..., 2024],
  )
  # возвращает DataFrame с колонками: country (ISO3 str), year (int), value (float)

== трансформация данных — используй готовые утилиты из src.tools.skills ==

from src.tools.skills import (
    rename_value_column,       # df = rename_value_column(df, "rdexpend_pct_gdp")
    filter_years,              # df = filter_years(df, [2015,2016,...,2023])
    join_on_year,              # df = join_on_year(df1, df2, how="outer")
    join_on_country_year,      # df = join_on_country_year(df1, df2, country_col="country")
    calculate_index_to_base,   # df = calculate_index_to_base(df, base_year=2015)
    calculate_per_capita,      # df = calculate_per_capita(df, "value", "population")
    save_dataset_with_metadata,
)

== сохранение результата ==
в конце скрипта ОБЯЗАТЕЛЬНО вызови save_dataset_with_metadata:
  csv_path, meta_path = save_dataset_with_metadata(
      df=final_df,
      output_dir=OUTPUT_DIR,
      metadata={
          "query": "...",
          "sources": ["dataset_id_1", ...],
          "indicators": ["indicator_name"],
      },
      filename="output_dataset",
  )
  print(f"saved: {csv_path}")

== объединение нескольких источников ==

ПРАВИЛО: выбирай метод по ситуации:

1. ОДИН показатель, разные периоды (priority_merge) → pd.concat + drop_duplicates:
  df = pd.concat([df_primary, df_supplementary], ignore_index=True)
  df = df.drop_duplicates(subset=["year"], keep="first")   # или ["country","year"]
  df = df.sort_values("year").reset_index(drop=True)
  НЕ используй join_on_year для одного и того же индикатора — получишь колонки _x/_y!

2. РАЗНЫЕ показатели, объединить в одну строку → join_on_year / join_on_country_year:
  df = join_on_year(df_gdp, df_population, how="outer")
  df = join_on_country_year(df_urban, df_fertility, country_col="country")
  Перед join убери дублирующиеся колонки: df = df.drop(columns=["source","extraction_date"], errors="ignore")

ВАЖНО: колонки source и extraction_date добавляй ТОЛЬКО ПОСЛЕ всех join/merge операций.

== работа с WB панельными данными (countryiso3=None) ==
WB-файлы содержат агрегаты (регионы, группы стран), поэтому могут быть дубли по (country, year).
ВСЕГДА дедублируй перед pivot и перед расчётом производных метрик:
  df = df.drop_duplicates(subset=["country", "year"], keep="first")
Вместо df.pivot() используй df.pivot_table(aggfunc="first") — это устойчиво к дублям.
""".strip()


def build_codegen_messages(
    user_query: str,
    research_design: dict[str, Any],
    datasets: list[dict[str, Any]],
    archive_root: str = "",
    assembly_plan: dict[str, Any] | None = None,
    output_dir: str = "",
) -> list[dict[str, str]]:
    archive_note = f"\nARCHIVE_ROOT = r\"{archive_root}\"" if archive_root else ""
    output_dir_note = f"\nOUTPUT_DIR = Path(r\"{output_dir}\")" if output_dir else "\nOUTPUT_DIR = Path(\"output_dataset\")"

    if assembly_plan:
        # Use the structured plan — LLM gets exact files, filters, and output schema
        sources_block = f"""
план сборки данных (следуй ему точно):
{json.dumps(assembly_plan, ensure_ascii=False, indent=2)}
""".strip()
    else:
        # Fallback: pass raw dataset list (pre-assembly_plan behaviour)
        compact_datasets = [
            {
                "id": d.get("id"),
                "title": d.get("title"),
                "source": d.get("source"),
                "indicator_code": d.get("indicator_code"),
                "file_path": d.get("file_path"),
                "format": d.get("format"),
                "time_period": d.get("time_period"),
                "geography": d.get("geography"),
            }
            for d in datasets
        ]
        sources_block = f"""
источники данных (file_path относителен ARCHIVE_ROOT):
{json.dumps(compact_datasets, ensure_ascii=False, indent=2)}
""".strip()

    user_prompt = f"""
напиши python-скрипт для следующего исследования.

запрос: {user_query}
{archive_note}{output_dir_note}

{sources_block}

производные метрики:
{json.dumps(research_design.get("derived_metrics", []), ensure_ascii=False, indent=2)}

ожидаемые визуализации:
{json.dumps(research_design.get("expected_visualizations", []), ensure_ascii=False, indent=2)}

важно:
- читай данные из локальных parquet-файлов по пути Path(ARCHIVE_ROOT) / file_path
- для каждого датасета добавляй колонки source (dataset_id) и extraction_date
- итоговый датасет должен иметь колонки из output_columns плана (если план передан)
""".strip()

    return [
        {"role": "system", "content": CODEGEN_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]