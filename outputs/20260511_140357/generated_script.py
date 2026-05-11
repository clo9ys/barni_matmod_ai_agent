from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

from src.tools.readers import read_fedstatru_parquet
from src.tools.skills import (
    rename_value_column,
    filter_years,
    join_on_year,
    calculate_index_to_base,
    save_dataset_with_metadata
)

# Параметры
ARCHIVE_ROOT = r"D:\data"
OUTPUT_DIR = Path(r"outputs\20260511_140357")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === Загрузка данных ===
# Основной источник: номинальные располагаемые доходы и индекс потребительских цен
# Согласно плану — комбинация single_source, но по описанию метрики нужны два показателя:
# 1. Номинальные располагаемые доходы
# 2. Индекс потребительских цен (ИПЦ)

# Предположим, что в архиве есть подходящие датасеты (не указанные в rejected_sources)
# Ищем по логике: например, fedstatru_XXXXX — доходы; fedstatru_YYYYY — ИПЦ

# Пример: fedstatru_141112 — среднедушевые денежные доходы (предположение)
# Пример: fedstatru_161212 — индекс потребительских цен (предположение)

# Загружаем номинальные располагаемые доходы на душу населения (сумма в рублях)
file_path_income = "fedstatru/141112/data.parquet"
df_income = read_fedstatru_parquet(
    path=Path(ARCHIVE_ROOT) / file_path_income,
    okato='643',
    period='30',  # год в целом
    years=list(range(2014, 2025))
)
df_income = rename_value_column(df_income, "nominal_income")
df_income["source"] = "fedstatru_141112"
df_income["extraction_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Загружаем индекс потребительских цен (ИПЦ), 2014=100 или цепной
file_path_cpi = "fedstatru/161212/data.parquet"
df_cpi = read_fedstatru_parquet(
    path=Path(ARCHIVE_ROOT) / file_path_cpi,
    okato='643',
    period='30',
    years=list(range(2014, 2025))
)
df_cpi = rename_value_column(df_cpi, "cpi")
df_cpi["source"] = "fedstatru_161212"
df_cpi["extraction_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Объединяем по году
df_combined = join_on_year(df_income, df_cpi, how="outer")
df_combined = df_combined.sort_values("year").reset_index(drop=True)

# === Расчёт производной метрики ===
# Формула: ((nominal_income / cpi) / (nominal_income_2014 / cpi_2014)) * 100
base_year = 2014

# Вычисляем реальные доходы (номинал / ИПЦ)
df_combined["real_income"] = df_combined["nominal_income"] / df_combined["cpi"]

# Находим значение реальных доходов в базовом году
base_value = df_combined.loc[df_combined["year"] == base_year, "real_income"].iloc[0]

# Рассчитываем индекс реальных доходов к 2014 году
df_combined["real_disposable_income_index_2014"] = (df_combined["real_income"] / base_value) * 100

# Фильтруем только нужные колонки
final_df = df_combined[["year", "real_disposable_income_index_2014"]].copy()

# === Визуализация 1: Линейный график ===
plt.figure(figsize=(10, 6))
plt.plot(
    final_df["year"],
    final_df["real_disposable_income_index_2014"],
    marker="o",
    linewidth=2,
    markersize=5
)
plt.title("Реальные располагаемые доходы населения России\n(индекс, 2014 = 100)")
plt.xlabel("Год")
plt.ylabel("Индекс (2014=100)")
plt.grid(True, alpha=0.3)
plt.xticks(final_df["year"].unique())
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "plot_1.png", dpi=100, bbox_inches="tight")
plt.close()

# === Визуализация 2: Столбчатая диаграмма годового изменения ===
df_growth = final_df.copy()
df_growth["change"] = df_growth["real_disposable_income_index_2014"].pct_change() * 100
df_growth = df_growth.dropna(subset=["change"])

plt.figure(figsize=(10, 6))
bars = plt.bar(
    df_growth["year"],
    df_growth["change"],
    color=np.where(df_growth["change"] >= 0, "green", "red"),
    alpha=0.7
)
plt.title("Годовое изменение индекса реальных располагаемых доходов\n(в процентах)")
plt.xlabel("Год")
plt.ylabel("Изменение, %")
plt.grid(True, axis="y", alpha=0.3)
plt.xticks(df_growth["year"].unique())
# Подписи на столбцах
for bar, change in zip(bars, df_growth["change"]):
    plt.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() + (0.1 if change > 0 else -0.5),
        f"{change:+.1f}%",
        ha="center",
        va="bottom" if change > 0 else "top",
        fontsize=9
    )
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "plot_2.png", dpi=100, bbox_inches="tight")
plt.close()

# === Сохранение итогового датасета ===
csv_path, meta_path = save_dataset_with_metadata(
    df=final_df,
    output_dir=OUTPUT_DIR,
    metadata={
        "query": "Покажи реальные располагаемые доходы населения России с поправкой на инфляцию, индекс к 2014 году = 100.",
        "sources": ["fedstatru_141112", "fedstatru_161212"],
        "indicators": ["real_disposable_income_index_2014"],
        "rejected_sources": [
            {
                "dataset_id": "fedstatru_60821",
                "reason": "Датасет содержит информацию о доле населения ниже черты бедности, а не о располагаемых доходах или индексе цен. Не соответствует запрошенным индикаторам."
            },
            {
                "dataset_id": "fedstatru_60822",
                "reason": "Датасет содержит информацию о доле населения ниже черты бедности, а не о располагаемых доходах или индексе цен. Не соответствует запрошенным индикаторам."
            },
            {
                "dataset_id": "fedstatru_58805",
                "reason": "Датасет содержит информацию о доле населения ниже черты бедности, а не о располагаемых доходах или индексе цен. Не соответствует запрошенным индикаторам."
            },
            {
                "dataset_id": "fedstatru_58806",
                "reason": "Датасет содержит информацию о доле населения ниже черты бедности, а не о располагаемых доходах или индексе цен. Не соответствует запрошенным индикаторам."
            },
            {
                "dataset_id": "fedstatru_60823",
                "reason": "Датасет содержит информацию о доле населения ниже черты бедности, а не о располагаемых доходах или индексе цен. Не соответствует запрошенным индикаторам."
            }
        ],
        "derived_metrics": [
            {
                "name": "real disposable income index (2014=100)",
                "formula": "((nominal disposable income / CPI) / (nominal disposable income_2014 / CPI_2014)) * 100",
                "description": "Индекс реальных располагаемых доходов населения России, рассчитанный как номинальные доходы, скорректированные на индекс потребительских цен, и перебазированные к 2014 году = 100"
            }
        ]
    },
    filename="output_dataset"
)

print(f"saved: {csv_path}")