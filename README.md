# AI-Assistant NSEDC

**Интеллектуальный агент для автоматизации полного цикла социально-экономических исследований от команды Барни**

Проект разработан в рамках VI Весенней школы «Информационные технологии и искусственный интеллект» по кейсу НЦСЭД.

---

## О проекте

AI-Assistant NSEDC — это ассистент для экономистов и исследователей, который превращает запрос на естественном языке в проверяемый набор исследовательских артефактов и итоговый датасет.

Пользователь может написать:

```text
Собери динамику ВВП России за 2014–2024 годы
```

Система проходит путь от запроса до результата:

```text
Query
→ Research Definition
→ RAG Search
→ Rerank
→ Research Design
→ Dataset Structure
→ Assembly Plan
→ Assembly Validation
→ Codegen
→ Execution
→ Output Validation
→ Dataset
```

Главная идея проекта:

```text
LLM планирует.
RAG ищет источники.
Validator проверяет.
Deterministic tools собирают данные.
```

То есть LLM не является источником фактов и чисел. Она помогает понять запрос, построить исследовательский дизайн, выбрать источники и сгенерировать код. Данные извлекаются детерминированным кодом из реальных файлов и источников.

---

## Проблема

Исследователь или экономист часто тратит большую часть времени не на анализ, а на подготовку данных:

1. поиск подходящих источников;
2. проверку релевантности датасетов;
3. работу с разными форматами;
4. согласование периодов, географии и единиц измерения;
5. объединение нескольких источников;
6. проверку полноты и качества результата.

Обычная LLM может сгенерировать красивый текстовый ответ, но в задачах с социально-экономическими данными этого недостаточно:

- модель может галлюцинировать факты и цифры;
- у ответа может не быть источников;
- результатом часто нужен не текст, а таблица;
- пользователь должен видеть, какие источники использовались и какие шаги были выполнены.

---

## Решение

Проект реализует **Hybrid Agentic Pipeline** — управляемый агентный пайплайн, который сочетает LLM и детерминированные инструменты.

Система:

- принимает запрос на естественном языке;
- извлекает параметры исследования;
- ищет релевантные источники через RAG;
- переоценивает найденные источники через reranker;
- строит research design;
- формирует структуру целевого датасета;
- строит assembly plan;
- валидирует plan по реальным файлам;
- генерирует Python-скрипт;
- запускает скрипт;
- проверяет итоговый датасет;
- сохраняет все промежуточные артефакты.

---

## Архитектура системы

```text
Пользователь
   ↓
Frontend [React / Vite]
   ↓ HTTP / SSE
Backend API [FastAPI]
   ↓
Core Pipeline / Agent-оркестратор
   ├── SQLite + SQLModel
   │      пользователи, сессии, статусы, trace
   │
   ├── LLM Client
   │      Qwen через Yandex AI Studio / OpenAI-compatible API
   │
   ├── RAG Layer
   │      registry_full.json → embeddings → FAISS
   │
   ├── Reranker
   │      переоценка релевантности найденных источников
   │
   ├── Tools / Skills Layer
   │      readers.py, skills.py, validator.py, output_validator.py
   │
   └── Executor / Sandbox
          generated_script.py → output_dataset.csv + metadata
```

---

## Ключевые особенности

### 1. Controlled Agentic Pipeline

В проекте используется не свободный агент, который сам бесконтрольно вызывает инструменты, а управляемая state-machine логика.

Pipeline умеет останавливаться, если:

- запрос неоднозначный;
- данных нет;
- найденные источники нерелевантны;
- assembly plan не проходит validation;
- generated script не создаёт корректный датасет.

### 2. RAG по метаданным

Система ищет не по сырым значениям, а по metadata cards датасетов.

В metadata card входят:

- название датасета;
- описание;
- источник;
- география;
- период;
- показатели;
- единицы измерения;
- структура;
- file path;
- tags.

Для поиска используется FAISS.

### 3. Reranker

После FAISS-поиска найденные кандидаты переоцениваются reranker-моделью.

FAISS отвечает за быстрый recall, reranker — за precision.

### 4. Assembly Plan

Перед генерацией кода система строит технический план сборки датасета.

Assembly plan содержит:

- какие источники использовать;
- какие файлы читать;
- какие фильтры применять;
- какие годы брать;
- как объединять данные;
- какие колонки получить на выходе;
- какие источники отвергнуты и почему.

### 5. Validation до Codegen

Перед генерацией кода assembly plan проверяется валидатором.

Validator проверяет:

- существует ли file path;
- читается ли файл;
- не пустой ли DataFrame;
- есть ли нужные годы;
- валидны ли фильтры.

Если plan невалиден, код не генерируется.

### 6. Deterministic Tools

LLM не извлекает значения из таблиц самостоятельно.

Для работы с данными используются deterministic tools:

- `readers.py` — чтение parquet-файлов World Bank и Fedstat/Rosstat;
- `skills.py` — фильтрация, join, метрики, сохранение результата;
- `validator.py` — проверка assembly plan;
- `output_validator.py` — проверка итогового датасета.

### 7. Trace Log

Пользователь может увидеть весь след работы ассистента:

- как система поняла запрос;
- какие источники нашла;
- какие источники выбрала;
- какой research design построила;
- какой assembly plan сгенерировала;
- прошёл ли plan validation;
- какой скрипт был сгенерирован;
- какой датасет получился на выходе.

---

## Пользовательский путь

### 1. Query

Пользователь вводит запрос на естественном языке.

Пример:

```text
Собери динамику ВВП России за 2014–2024 годы
```

### 2. Research Definition

LLM извлекает структурированное описание запроса:

- тип запроса;
- география;
- временной период;
- показатели;
- единицы измерения;
- фильтры;
- необходимость уточнений;
- уточняющие вопросы.

Если запрос неполный, pipeline возвращает:

```text
status = "needs_clarification"
```

Если данных по теме нет, pipeline возвращает:

```text
status = "no_data"
```

### 3. RAG Search

Система ищет релевантные датасеты в metadata registry.

Используются:

- `registry.json` — маленький куратированный реестр для локальной проверки;
- `registry_full.json` — расширенный реестр;
- FAISS;
- sentence-transformers embeddings.

### 4. Rerank

Найденные кандидаты переоцениваются reranker-моделью.

Если лучший источник не набирает достаточный score, pipeline возвращает:

```text
status = "no_data"
```

### 5. Research Design

LLM формирует смысловой дизайн исследования:

- исследовательские вопросы;
- гипотезы;
- нужные индикаторы;
- производные метрики;
- ограничения;
- ожидаемую структуру результата.

### 6. Dataset Structure

Система формирует структуру целевого датасета:

- зернистость строк;
- измерения;
- показатели;
- типы колонок;
- единицы измерения.

Артефакт сохраняется как:

```text
outputs/<session_id>/dataset_structure.json
```

### 7. Assembly Plan

LLM строит технический план сборки:

- `primary_sources`;
- `dataset_id`;
- `file_path`;
- `source_id`;
- `filters`;
- `years_used`;
- `join_key`;
- `output_columns`;
- `rejected_sources`.

### 8. Assembly Validation

План проверяется через validator.

Если план не проходит проверку, pipeline возвращает:

```text
status = "validation_failed"
```

### 9. Codegen

LLM генерирует Python-скрипт по проверенному assembly plan.

Скрипт сохраняется как:

```text
outputs/<session_id>/generated_script.py
```

### 10. Execution

Executor запускает generated script и ожидает появление:

```text
outputs/<session_id>/output_dataset.csv
outputs/<session_id>/output_dataset_metadata.json
```

### 11. Output Validation

Output validator проверяет итоговый датасет:

- файл существует;
- CSV читается;
- таблица не пустая;
- есть ожидаемые колонки;
- indicator columns не полностью пустые.

Результат сохраняется как:

```text
outputs/<session_id>/output_validation.json
```

### 12. Dataset

Пользователь получает:

- итоговый датасет;
- metadata;
- generated script;
- trace всех шагов.

---

## Технологический стек

### Backend

- FastAPI
- Uvicorn
- SSE / streaming
- SQLModel
- SQLAlchemy
- SQLite
- Pydantic
- python-jose
- passlib / bcrypt

### Frontend

- React
- Vite
- fetch-event-source

### ML / AI

- Qwen через Yandex AI Studio
- OpenAI-compatible API
- OpenAI Python SDK
- sentence-transformers
- FAISS
- reranker model

### Data

- pandas
- pyarrow
- parquet
- numpy
- matplotlib

### Tests

- pytest

---

## Структура проекта

```text
barni_matmod_ai_agent/
├── data/
│   ├── registry.json
│   ├── registry_full.json
│   ├── index/
│   └── index_full/
│
├── outputs/
│   └── <session_id>/
│       ├── research_definition.json
│       ├── retrieved_datasets.json
│       ├── reranked_datasets.json
│       ├── research_design.json
│       ├── dataset_structure.json
│       ├── assembly_plan.json
│       ├── validation_report.json
│       ├── generated_script.py
│       ├── output_dataset.csv
│       ├── output_dataset_metadata.json
│       └── output_validation.json
│
├── src/
│   ├── core/
│   │   ├── pipeline.py
│   │   ├── artifacts.py
│   │   ├── executor.py
│   │   ├── database.py
│   │   ├── security.py
│   │   └── state.py
│   │
│   ├── ml/
│   │   ├── model.py
│   │   ├── prompts.py
│   │   ├── rag.py
│   │   ├── reranker.py
│   │   └── codegen.py
│   │
│   ├── tools/
│   │   ├── readers.py
│   │   ├── skills.py
│   │   ├── validator.py
│   │   ├── output_validator.py
│   │   └── preprocessing.py
│   │
│   └── interface/
│       └── frontend / backend interface files
│
├── tests/
├── evaluate.py
├── run_pipeline.py
├── pyproject.toml
├── uv.lock
└── README.md
```

---

## Быстрый старт

### 1. Клонировать репозиторий

```bash
git clone https://github.com/clo9ys/barni_matmod_ai_agent.git
cd barni_matmod_ai_agent
```

Если основная работа ведётся в ветке `develop`:

```bash
git checkout develop
git pull origin develop
```

### 2. Установить uv

Если `uv` ещё не установлен:

```bash
pip install uv
```

Проверить установку:

```bash
uv --version
```

### 3. Установить зависимости

```bash
uv sync
```

### 4. Создать `.env`

Создайте файл `.env` в корне проекта.

Пример:

```env
AI_API_KEY=your_yandex_ai_studio_key
AI_BASE_URL=https://llm.api.cloud.yandex.net/foundationModels/v1/api/openai/
AI_MODEL=gpt://<folder_id>/qwen-max/latest

JWT_SECRET=your_random_secret

ARCHIVE_ROOT=D:\data
OUTPUTS_ROOT=outputs
```

Назначение переменных:

```text
AI_API_KEY      ключ для LLM API
AI_BASE_URL     OpenAI-compatible endpoint
AI_MODEL        модель Qwen / Yandex AI Studio
JWT_SECRET      секрет для JWT
ARCHIVE_ROOT    путь к локальному архиву parquet-файлов
OUTPUTS_ROOT    папка для артефактов pipeline
```

Файл `.env` не должен попадать в GitHub.

### 5. Построить FAISS index

Для маленького реестра:

```bash
uv run python -m src.ml.rag build
```

Проверить поиск:

```bash
uv run python -m src.ml.rag search "Сравни динамику ВВП стран Европы за 2020-2025"
```

Ожидаемый результат — список найденных датасетов с `id`, `source`, `score`, `url` и `description`.

### 6. Запустить core pipeline из CLI

```bash
uv run python run_pipeline.py "Собери динамику ВВП России за 2014-2024 годы"
```

После запуска проверьте папку:

```text
outputs/<session_id>/
```

Там должны появиться промежуточные артефакты, например:

```text
research_definition.json
retrieved_datasets.json
reranked_datasets.json
research_design.json
dataset_structure.json
assembly_plan.json
validation_report.json
generated_script.py
```

Если execution прошёл успешно:

```text
output_dataset.csv
output_dataset_metadata.json
output_validation.json
```

### 7. Запустить backend

```bash
uv run uvicorn src.interface.main:app --reload --port 8000
```

API будет доступен по адресу:

```text
http://127.0.0.1:8000
```

### 8. Запустить frontend

Перейдите в папку frontend:

```bash
cd src/interface
npm install
npm run dev
```

Vite покажет локальный адрес приложения.

---

## Основные команды

### Проверить статус Git

```bash
git status
```

### Запустить тесты

```bash
uv run pytest
```

### Запустить конкретные тесты

```bash
uv run pytest tests/test_validator.py
```

### Пересобрать RAG index

```bash
uv run python -m src.ml.rag build
```

### Проверить поиск по registry

```bash
uv run python -m src.ml.rag search "ВВП России за 2014-2024"
```

### Запустить pipeline

```bash
uv run python run_pipeline.py "Динамика ВВП России на душу населения за 2010-2023 годы"
```

---

## Артефакты pipeline

После запуска создаётся папка:

```text
outputs/<session_id>/
```

| Файл | Что содержит |
|---|---|
| `research_definition.json` | структурированное понимание запроса |
| `retrieved_datasets.json` | кандидаты после FAISS |
| `reranked_datasets.json` | источники после reranker |
| `research_design.json` | гипотезы, индикаторы, метрики, ограничения |
| `dataset_structure.json` | структура целевого датасета |
| `assembly_plan.json` | технический план сборки |
| `validation_report.json` | результат проверки assembly plan |
| `generated_script.py` | сгенерированный Python-скрипт |
| `output_dataset.csv` | итоговый датасет |
| `output_dataset_metadata.json` | метаданные итогового датасета |
| `output_validation.json` | результат проверки итогового датасета |

---

## Stop logic

Pipeline не всегда идёт до конца. Это осознанное поведение.

### `needs_clarification`

Возвращается, если запрос неполный.

Пример:

```text
дай данные по инфляции
```

Система должна уточнить:

```text
по какой стране?
за какой период?
какой показатель инфляции нужен?
```

### `no_data`

Возвращается, если подходящие данные не найдены или релевантность источников слишком низкая.

### `validation_failed`

Возвращается, если assembly plan не проходит проверку.

Примеры причин:

```text
файл не найден
нет строк с нужным period
нет нужных годов
DataFrame пустой
```

### `output_validation_failed`

Возвращается, если скрипт выполнился, но итоговый датасет не соответствует ожиданиям.

Примеры причин:

```text
output_dataset.csv не создан
CSV пустой
нет ожидаемых колонок
indicator column полностью пустая
```

---

## Основные модули

### `src/core/pipeline.py`

Главный orchestrator.

Управляет цепочкой:

```text
extract params
→ RAG
→ rerank
→ research design
→ assembly plan
→ validation
→ codegen
→ execution
→ output validation
```

### `src/ml/model.py`

LLM client через OpenAI-compatible API.

Основные функции:

```text
complete_text()
complete_json()
is_llm_configured()
```

### `src/ml/rag.py`

FAISS-based retrieval по metadata registry.

Основные функции:

```text
build_index()
search_datasets()
```

### `src/ml/reranker.py`

Reranker для переоценки найденных датасетов после FAISS.

### `src/ml/prompts.py`

Промпты для LLM-шагов:

```text
extract params
research design
assembly plan
codegen
metadata enrichment
```

### `src/ml/codegen.py`

Обёртка генерации Python-кода.

Генерирует чистый `.py`-скрипт без markdown fences.

### `src/tools/readers.py`

Deterministic readers для parquet-данных:

```text
read_fedstatru_parquet()
read_wb_parquet()
read_fedstatru_coverage()
read_fedstatru_periods()
```

### `src/tools/skills.py`

Переиспользуемые deterministic primitives для generated scripts:

```text
rename_value_column()
filter_years()
join_on_year()
join_on_country_year()
calculate_index_to_base()
calculate_per_capita()
save_dataset_with_metadata()
```

### `src/tools/validator.py`

Валидация assembly plan до генерации кода.

### `src/tools/output_validator.py`

Валидация итогового CSV после выполнения generated script.

### `src/core/artifacts.py`

Сохранение промежуточных артефактов в:

```text
outputs/<session_id>/
```

### `src/core/executor.py`

Запуск `generated_script.py`, сбор stdout/stderr и поиск output-файлов.

---

## Пример demo-flow

Запрос:

```text
Собери динамику ВВП России за 2014-2024 годы
```

Ожидаемый flow:

```text
1. LLM извлекает:
   geography = Russia
   time_period = 2014-2024
   indicators = GDP

2. RAG находит подходящие датасеты.

3. Reranker выбирает наиболее релевантные источники.

4. LLM формирует research_design.

5. LLM строит assembly_plan:
   source
   file_path
   filters
   years_used
   output_columns

6. Validator проверяет plan.

7. Codegen создаёт generated_script.py.

8. Executor запускает скрипт.

9. Output validator проверяет output_dataset.csv.

10. Пользователь получает dataset + metadata + script + trace.
```

---

## Тестирование

Запустить все тесты:

```bash
uv run pytest
```

Тесты покрывают:

- stop-logic;
- no-data;
- needs-clarification;
- validator;
- missing files;
- empty DataFrame;
- missing years;
- happy path.

---

## Ограничения текущей версии

- Качество end-to-end зависит от полноты `registry_full.json` и локального архива данных.
- Для корректной сборки датасета нужен правильно заданный `ARCHIVE_ROOT`.
- Generated script может не пройти execution на сложных multi-source запросах.
- Reranker threshold пока эвристический и требует калибровки на тест-кейсах.
- Для финальной оценки нужны стабильные 5–8 end-to-end demo-кейсов и расширенный evaluation.
- Fine-tuning, графовая БД и сложная оптимизация большого индекса не входят в текущий MVP.

---

## Roadmap

Ближайшие задачи:

- стабилизировать 5–8 end-to-end demo-кейсов;
- обновить `evaluate.py`;
- зафиксировать тестовый набор пользовательских запросов;
- расширить skills library;
- улучшить matching географии и страновых алиасов;
- откалибровать reranker threshold;
- расширить output validation;
- улучшить README и инструкции запуска.

---

## Команда

- **Team Lead / Backend Engineer** — архитектура, API, DB, authorization.
- **ML / AI Engineer** — LLM, RAG, prompts, FAISS, reranker, research design, assembly plan.
- **Data Engineer** — registry, parquet readers, preprocessing, validation, skills.
- **Frontend Engineer** — React/Vite UI, trace, artifacts, SSE integration.
- **Product / Demo** — сценарии, презентация, пользовательский путь.

---

## Ключевая идея

```text
Мы сделали не чат-бота, а воспроизводимый pipeline
от исследовательского запроса до проверяемого датасета.
```
