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
OUTPUT_DIR = Path(r"outputs\20260511_124432")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === Загрузка и обработка данных ===

# Основной источник: fedstatru_62685 (2018–2024)
df_main = read_fedstatru_parquet(
    path=Path(ARCHIVE_ROOT) / "fedstatru/data/parquet/62685.parquet",
    okato="643",
    period="1558883",
    years=[2018, 2019, 2020, 2021, 2022, 2023, 2024]
)
df_main = rename_value_column(df_main, "inflation_cpi_percent")
df_main["source"] = "fedstatru_62685"
df_main["extraction_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Дополнительный источник: fedstatru_55396 (2014–2017)
df_supp = read_fedstatru_parquet(
    path=Path(ARCHIVE_ROOT) / "fedstatru/data/parquet/55396.parquet",
    okato="643",
    period="744",
    years=[2014, 2015, 2016, 2017]
)
df_supp = rename_value_column(df_supp, "inflation_cpi_percent")
df_supp["source"] = "fedstatru_55396"
df_supp["extraction_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Удаляем служебные колонки перед объединением
df_main_clean = df_main.drop(columns=["source", "extraction_date"], errors="ignore")
df_supp_clean = df_supp.drop(columns=["source", "extraction_date"], errors="ignore")

# Объединение: сначала основной, потом дополнительный (приоритет у основного)
df_combined = join_on_year(df_main_clean, df_supp_clean, how="outer")

# Восстанавливаем source и extraction_date из обоих датасетов
df_combined = df_combined.merge(
    df_main[["year", "source", "extraction_date"]], on="year", how="left", suffixes=("", "_main")
)
supp_temp = df_supp[["year", "source", "extraction_date"]].copy()
supp_temp = supp_temp.rename(columns={"source": "source_supp", "extraction_date": "extraction_date_supp"})
df_combined = df_combined.merge(supp_temp, on="year", how="left")

# Заполняем пропущенные значения из дополнительного источника
df_combined["source"] = df_combined["source"].fillna(df_combined["source_supp"])
df_combined["extraction_date"] = df_combined["extraction_date"].fillna(df_combined["extraction_date_supp"])
df_combined = df_combined.drop(columns=["source_supp", "extraction_date_supp"])

# Сортировка по году
df_combined = df_combined.sort_values(by="year").reset_index(drop=True)

# Переименовываем колонки в соответствии с output_columns
final_df = df_combined[["year", "inflation_cpi_percent", "source", "extraction_date"]].copy()

# === Расчет производных метрик ===

# Среднегодовая инфляция
avg_inflation = final_df["inflation_cpi_percent"].mean()

# Кумулятивная инфляция
cpi_factors = (1 + final_df["inflation_cpi_percent"] / 100)
cumulative_inflation = (np.prod(cpi_factors) - 1) * 100

# Вывод метрик
print(f"Среднегодовая инфляция (2014–2024): {avg_inflation:.2f}%")
print(f"Кумулятивная инфляция (2014–2024): {cumulative_inflation:.2f}%")

# === Визуализация ===

# 1. Линейный график динамики годовой инфляции
plt.figure(figsize=(12, 6))
plt.plot(final_df["year"], final_df["inflation_cpi_percent"], marker="o", linestyle="-", color="tab:blue")
plt.title("Динамика годовой инфляции в России (ИПЦ, % к предыдущему году), 2014–2024")
plt.xlabel("Год")
plt.ylabel("Инфляция, %")
plt.grid(True, alpha=0.3)
plt.xticks(final_df["year"].unique())
plt.ylim(bottom=0)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "plot_1.png", dpi=100, bbox_inches="tight")
plt.close()

# 2. Столбчатая диаграмма годовых значений
plt.figure(figsize=(14, 6))
bars = plt.bar(final_df["year"], final_df["inflation_cpi_percent"], color="tab:orange", alpha=0.8)
plt.title("Годовые значения инфляции в России (ИПЦ), 2014–2024")
plt.xlabel("Год")
plt.ylabel("Инфляция, %")
plt.xticks(final_df["year"].unique())
plt.ylim(bottom=0)
# Подписи на столбцах
for bar, value in zip(bars, final_df["inflation_cpi_percent"]):
    plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.1, f"{value:.1f}",
             ha='center', va='bottom', fontsize=9)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "plot_2.png", dpi=100, bbox_inches="tight")
plt.close()

# 3. Таблица с данными и кумулятивной инфляцией
summary_table = final_df[["year", "inflation_cpi_percent"]].copy()
summary_table["inflation_cpi_percent"] = summary_table["inflation_cpi_percent"].round(2)
summary_table["description"] = ""
summary_table.loc[0, "description"] = "Годовая инфляция, %"
summary_table = summary_table[["year", "inflation_cpi_percent", "description"]]

# Добавим строку с кумулятивной инфляцией
cum_row = pd.DataFrame([{
    "year": "2014–2024",
    "inflation_cpi_percent": round(cumulative_inflation, 2),
    "description": "Кумулятивная инфляция, %"
}])
summary_table = pd.concat([summary_table, cum_row], ignore_index=True)

table_path = OUTPUT_DIR / "inflation_table.csv"
summary_table.to_csv(table_path, index=False)
print(f"Таблица с данными сохранена: {table_path}")

# === Сохранение итогового датасета ===

csv_path, meta_path = save_dataset_with_metadata(
    df=final_df,
    output_dir=OUTPUT_DIR,
    metadata={
        "query": "Динамика инфляции в России (индекс потребительских цен) за 2014–2024 годы, годовые значения",
        "sources": ["fedstatru_62685", "fedstatru_55396"],
        "indicators": ["inflation_cpi_percent"],
        "derived_metrics": {
            "average_annual_inflation_percent": round(avg_inflation, 2),
            "cumulative_inflation_percent": round(cumulative_inflation, 2)
        }
    },
    filename="output_dataset"
)

print(f"saved: {csv_path}")