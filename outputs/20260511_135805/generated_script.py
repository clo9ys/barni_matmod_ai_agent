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
OUTPUT_DIR = Path(r"outputs\20260511_135805")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === Загрузка данных ===
# Основной источник
df_primary = read_fedstatru_parquet(
    path=Path(ARCHIVE_ROOT) / "fedstatru/data/parquet/55396.parquet",
    okato="643",
    period="744",
    years=[2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]
)
df_primary = rename_value_column(df_primary, "cpi_change_percent")
df_primary["source"] = "fedstatru_55396"
df_primary["extraction_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Дополнительный источник
df_supplementary = read_fedstatru_parquet(
    path=Path(ARCHIVE_ROOT) / "fedstatru/data/parquet/62685.parquet",
    okato="643",
    period="1558883",
    years=[2018, 2019, 2020, 2021, 2022, 2023, 2024]
)
df_supplementary = rename_value_column(df_supplementary, "cpi_change_percent")
df_supplementary["source"] = "fedstatru_62685"
df_supplementary["extraction_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# === Объединение данных (priority_merge) ===
# Объединяем: сначала основной, потом дополнительный (перезапись не требуется — keep="first")
df_combined = pd.concat([df_primary[["year", "cpi_change_percent", "source", "extraction_date"]],
                         df_supplementary[["year", "cpi_change_percent", "source", "extraction_date"]]],
                        ignore_index=True)
df_combined = df_combined.drop_duplicates(subset=["year"], keep="first")
df_combined = df_combined.sort_values("year").reset_index(drop=True)

# === Производные метрики ===
# В данном случае данные уже представляют собой годовой темп изменения (%), поэтому пересчёт не требуется.
# Но если бы был уровень ИПЦ (индекс), тогда:
# df_combined["inflation_rate"] = df_combined["cpi_change_percent"]  # уже в процентах

# === Визуализации ===
# 1. Линейный график динамики годового темпа инфляции
plt.figure(figsize=(12, 6))
plt.plot(df_combined["year"], df_combined["cpi_change_percent"], marker='o', linestyle='-', color='tab:blue')
plt.title("Динамика годового темпа инфляции в России (2014–2024)")
plt.xlabel("Год")
plt.ylabel("Темп инфляции, %")
plt.grid(True, alpha=0.3)
plt.xticks(df_combined["year"].unique())
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "plot_1.png", dpi=100, bbox_inches="tight")
plt.close()

# 2. Столбчатая диаграмма годовых значений ИПЦ
plt.figure(figsize=(12, 6))
bars = plt.bar(df_combined["year"], df_combined["cpi_change_percent"], color='tab:orange', alpha=0.8)
plt.title("Годовые значения индекса потребительских цен (в % к предыдущему году)")
plt.xlabel("Год")
plt.ylabel("Изменение, %")
plt.xticks(df_combined["year"].unique())
plt.grid(True, axis='y', alpha=0.3)

# Подписи на столбцах
for bar in bars:
    height = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
             f'{height:.1f}', ha='center', va='bottom', fontsize=9)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / "plot_2.png", dpi=100, bbox_inches="tight")
plt.close()

# === Формирование итогового датасета ===
final_df = df_combined[["year", "cpi_change_percent"]].copy()

# Сохранение с метаданными
csv_path, meta_path = save_dataset_with_metadata(
    df=final_df,
    output_dir=OUTPUT_DIR,
    metadata={
        "query": "Покажи динамику инфляции в России (индекс потребительских цен) за 2014–2024 годы, годовые значения.",
        "sources": ["fedstatru_55396", "fedstatru_62685"],
        "indicators": ["cpi_change_percent"],
        "combination_strategy": "priority_merge",
        "description": "Годовой темп инфляции в России, % к предыдущему году"
    },
    filename="output_dataset"
)

print(f"saved: {csv_path}")