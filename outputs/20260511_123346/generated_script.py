from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

from src.tools.readers import read_wb_parquet
from src.tools.skills import (
    rename_value_column,
    filter_years,
    join_on_country_year,
    calculate_index_to_base,
    save_dataset_with_metadata
)

# Параметры
ARCHIVE_ROOT = r"D:\data"
OUTPUT_DIR = Path(r"outputs\20260511_123346")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === Загрузка данных ===
# Первичный источник: доля городского населения
file_path_urban = "wb/parquet/SP.URB.TOTL.IN.ZS.parquet"
df_urban = read_wb_parquet(
    path=Path(ARCHIVE_ROOT) / file_path_urban,
    countryiso3=None,
    years=list(range(2010, 2023))
)
df_urban = rename_value_column(df_urban, "urban_population_share")
df_urban = df_urban.drop_duplicates(subset=["country", "year"], keep="first")
df_urban["source"] = "wb_sp_urb_totl_in_zs"
df_urban["extraction_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Второй источник: общий коэффициент рождаемости (total fertility rate)
file_path_fertility = "wb/parquet/SP.DYN.TFRT.IN.parquet"
df_fertility = read_wb_parquet(
    path=Path(ARCHIVE_ROOT) / file_path_fertility,
    countryiso3=None,
    years=list(range(2010, 2023))
)
df_fertility = rename_value_column(df_fertility, "total_fertility_rate")
df_fertility = df_fertility.drop_duplicates(subset=["country", "year"], keep="first")
df_fertility["source"] = "wb_sp_dyn_tfrt_in"
df_fertility["extraction_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Убираем вспомогательные колонки перед объединением
df_urban_clean = df_urban.drop(columns=["source", "extraction_date"], errors="ignore")
df_fertility_clean = df_fertility.drop(columns=["source", "extraction_date"], errors="ignore")

# Объединение по стране и году
df_combined = join_on_country_year(df_urban_clean, df_fertility_clean, country_col="country")

# Фильтрация по годам (уже была, но на всякий случай)
df_combined = filter_years(df_combined, list(range(2010, 2023)))

# === Производные метрики: изменения за период ===
# Вычисляем изменения за период 2010–2022 по странам
df_pivot_urban = df_combined.pivot_table(
    index="country", columns="year", values="urban_population_share", aggfunc="first"
)
df_pivot_fertility = df_combined.pivot_table(
    index="country", columns="year", values="total_fertility_rate", aggfunc="first"
)

# Изменение за период
delta_urban = df_pivot_urban[2022] - df_pivot_urban[2010]
delta_fertility = df_pivot_fertility[2022] - df_pivot_fertility[2010]

# DataFrame с изменениями
df_change = pd.DataFrame({
    "urbanization_change": delta_urban,
    "fertility_change": delta_fertility
}).dropna()

# Добавляем средние значения за период для анализа
df_avg = df_combined.groupby("country")[["urban_population_share", "total_fertility_rate"]].mean().dropna()

# === Визуализации ===

# 1. Панельные линейные графики: urban_population_share и total_fertility_rate
countries_sample = df_combined["country"].unique()[:10]  # первые 10 стран для наглядности
df_sample = df_combined[df_combined["country"].isin(countries_sample)]

fig, axes = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

# Урбанизация
for country in countries_sample:
    data = df_sample[df_sample["country"] == country]
    axes[0].plot(data["year"], data["urban_population_share"], label=country, alpha=0.7)
axes[0].set_ylabel("Urban Population Share (%)")
axes[0].set_title("Динамика доли городского населения (2010–2022)")
axes[0].legend(loc="lower right", fontsize="small")
axes[0].grid(True, alpha=0.3)

# Рождаемость
for country in countries_sample:
    data = df_sample[df_sample["country"] == country]
    axes[1].plot(data["year"], data["total_fertility_rate"], label=country, alpha=0.7)
axes[1].set_ylabel("Total Fertility Rate (births per woman)")
axes[1].set_xlabel("Year")
axes[1].set_title("Динамика общего коэффициента рождаемости (2010–2022)")
axes[1].legend(loc="lower right", fontsize="small")
axes[1].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(OUTPUT_DIR / "plot_1.png", dpi=100, bbox_inches="tight")
plt.close()

# 2. Диаграмма рассеяния: средние значения за период
plt.figure(figsize=(10, 6))
plt.scatter(df_avg["urban_population_share"], df_avg["total_fertility_rate"], alpha=0.6)
z = np.polyfit(df_avg["urban_population_share"], df_avg["total_fertility_rate"], 1)
p = np.poly1d(z)
plt.plot(df_avg["urban_population_share"], p(df_avg["urban_population_share"]), color="red", linestyle="--", label="Trend line")
plt.xlabel("Average Urban Population Share (%)")
plt.ylabel("Average Total Fertility Rate")
plt.title("Средняя урбанизация vs рождаемость (2010–2022)")
plt.grid(True, alpha=0.3)
plt.legend()
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "plot_2.png", dpi=100, bbox_inches="tight")
plt.close()

# 3. Тепловая карта изменений по регионам
# Загрузим региональные данные (агрегаты WB: например, регионы по кодам)
regions = ['EAS', 'ECS', 'LCN', 'MNA', 'NAC', 'SAS', 'SSF', 'ECA', 'OED']  # пример региональных кодов
region_names = {
    'EAS': 'East Asia & Pacific',
    'ECS': 'Europe & Central Asia',
    'LCN': 'Latin America & Caribbean',
    'MNA': 'Middle East & North Africa',
    'NAC': 'North America',
    'SAS': 'South Asia',
    'SSF': 'Sub-Saharan Africa',
    'ECA': 'Europe and Central Asia (excluding high income)',
    'OED': 'High income'
}

df_regions = df_change.reset_index()
df_regions["region"] = df_regions["country"].map(region_names)
df_regions_filtered = df_regions[df_regions["region"].notna()]

# Средние изменения по регионам
df_region_change = df_regions_filtered.groupby("region")[["urbanization_change", "fertility_change"]].mean()

# Тепловая карта
plt.figure(figsize=(8, 6))
plt.imshow(df_region_change.T, cmap="coolwarm", aspect="auto", vmin=-10, vmax=10)
plt.colorbar(label="Change over 2010–2022")
plt.xticks(np.arange(len(df_region_change)), df_region_change.index, rotation=45)
plt.yticks(np.arange(2), ['Δ Urbanization', 'Δ Fertility'])
plt.title("Изменения показателей по регионам (2010–2022)")
for i, region in enumerate(df_region_change.index):
    plt.text(i, 0, f"{df_region_change.loc[region, 'urbanization_change']:.2f}",
             ha="center", va="center", color="black", fontsize=9)
    plt.text(i, 1, f"{df_region_change.loc[region, 'fertility_change']:.2f}",
             ha="center", va="center", color="black", fontsize=9)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "plot_3.png", dpi=100, bbox_inches="tight")
plt.close()

# 4. График с двойной осью для одной страны (пример: Россия)
country_example = "RUS"
df_country = df_combined[df_combined["country"] == country_example]

if not df_country.empty:
    fig, ax1 = plt.subplots(figsize=(10, 6))

    color = 'tab:blue'
    ax1.set_xlabel('Year')
    ax1.set_ylabel('Urban Population Share (%)', color=color)
    ax1.plot(df_country['year'], df_country['urban_population_share'], color=color, marker='o', label='Urban Share')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.set_title(f"Динамика по стране: {country_example}")

    ax2 = ax1.twinx()
    color = 'tab:red'
    ax2.set_ylabel('Total Fertility Rate', color=color)
    ax2.plot(df_country['year'], df_country['total_fertility_rate'], color=color, marker='s', label='Fertility Rate')
    ax2.tick_params(axis='y', labelcolor=color)

    fig.tight_layout()
    plt.savefig(OUTPUT_DIR / "plot_4.png", dpi=100, bbox_inches="tight")
    plt.close()

# === Формирование итогового датасета ===
final_df = df_combined[["country", "year", "urban_population_share", "total_fertility_rate"]].copy()

# Добавим колонки source и extraction_date в итоговый датасет (после всех операций)
final_df["source"] = "wb_sp_urb_totl_in_zs,wb_sp_dyn_tfrt_in"
final_df["extraction_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Сохранение результата
csv_path, meta_path = save_dataset_with_metadata(
    df=final_df,
    output_dir=OUTPUT_DIR,
    metadata={
        "query": "Динамика доли городского населения и общего коэффициента рождаемости по странам мира за 2010–2022. Источник: World Bank.",
        "sources": ["wb_sp_urb_totl_in_zs", "wb_sp_dyn_tfrt_in"],
        "indicators": ["urban_population_share", "total_fertility_rate"],
        "combination_strategy": "join_on_country_year",
        "years_used": list(range(2010, 2023)),
        "derived_metrics": [
            "urbanization_fertility_change: Δ(urban_population_share) vs Δ(total_fertility_rate) per country over 2010–2022"
        ]
    },
    filename="output_dataset"
)

print(f"saved: {csv_path}")