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
    save_dataset_with_metadata,
)
import warnings

warnings.filterwarnings("ignore")

# Пути
ARCHIVE_ROOT = r"D:\data"
OUTPUT_DIR = Path(r"outputs\20260511_121440")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === ЗАГРУЗКА ДАННЫХ ===

# Основной источник: доля городского населения
file_path_urban = "wb/parquet/SP.URB.TOTL.IN.ZS.parquet"
df_urban = read_wb_parquet(
    path=Path(ARCHIVE_ROOT) / file_path_urban,
    countryiso3=None,
    years=[2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
)
df_urban = rename_value_column(df_urban, "urban_population_share")
df_urban["source"] = "wb_sp_urb_totl_in_zs"
df_urban["extraction_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Загрузка общего коэффициента рождаемости (TFR)
file_path_fertility = "wb/parquet/SP.DYN.TFRT.IN.parquet"
df_fertility = read_wb_parquet(
    path=Path(ARCHIVE_ROOT) / file_path_fertility,
    countryiso3=None,
    years=[2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
)
df_fertility = rename_value_column(df_fertility, "total_fertility_rate")
df_fertility["source"] = "wb_sp_dyn_tfrt_in"
df_fertility["extraction_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# === ОБЪЕДИНЕНИЕ ДАННЫХ ===
df_combined = join_on_country_year(df_urban, df_fertility, country_col="country")

# Фильтрация по годам (уже отфильтровано при загрузке, но на всякий случай)
df_combined = filter_years(df_combined, [2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022])

# Убедимся, что колонки соответствуют плану
final_df = df_combined[["country", "year", "urban_population_share", "total_fertility_rate"]].copy()

# === РАСЧЁТ ПРОИЗВОДНЫХ МЕТРИК ===

# 1. Изменение показателей за 2010–2022 по странам
df_pivot_urban = final_df.pivot(index="country", columns="year", values="urban_population_share")
df_pivot_fertility = final_df.pivot(index="country", columns="year", values="total_fertility_rate")

# Изменение за период
change_urban = df_pivot_urban[2022] - df_pivot_urban[2010]
change_fertility = df_pivot_fertility[2022] - df_pivot_fertility[2010]

# Объединяем изменения
df_change = pd.DataFrame({
    "urbanization_change": change_urban,
    "fertility_change": change_fertility
}).reset_index()

# Добавляем метрику изменения
final_df = final_df.merge(
    df_change.rename(columns={"urbanization_change": "urbanization_fertility_change_2010_2022"}),
    on="country",
    how="left"
)

# 2. Ежегодная корреляция между урбанизацией и рождаемостью
annual_corr = final_df.groupby("year").apply(
    lambda x: x[["urban_population_share", "total_fertility_rate"]].corr(method="pearson").iloc[0,1]
).reset_index(name="correlation_urban_fertility_annual")

# Расширяем до всех строк (для сохранения в датасет)
final_df = final_df.merge(annual_corr, on="year", how="left")

# === ВИЗУАЛИЗАЦИИ ===

# 1. Линейный график динамики по странам (выберем топ-10 по населению или просто пример)
countries_sample = final_df.groupby("country").size().nlargest(10).index
df_sample = final_df[final_df["country"].isin(countries_sample)]

fig, ax1 = plt.subplots(figsize=(12, 6))
for country in df_sample["country"].unique():
    data = df_sample[df_sample["country"] == country].sort_values("year")
    ax1.plot(data["year"], data["urban_population_share"], label=f'{country} (urban)', linestyle='-', alpha=0.8)
ax1.set_xlabel("Год")
ax1.set_ylabel("Доля городского населения (%)", color='tab:blue')
ax1.tick_params(axis='y', labelcolor='tab:blue')
ax1.set_title("Динамика урбанизации и рождаемости по странам (2010–2022)")

ax2 = ax1.twinx()
for country in df_sample["country"].unique():
    data = df_sample[df_sample["country"] == country].sort_values("year")
    ax2.plot(data["year"], data["total_fertility_rate"], label=f'{country} (fertility)', linestyle='--', alpha=0.6)
ax2.set_ylabel("Коэффициент рождаемости", color='tab:orange')
ax2.tick_params(axis='y', labelcolor='tab:orange')
fig.tight_layout()
plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
plt.title("Динамика urban_population_share и total_fertility_rate")
plt.tight_layout()
plt.show()

# 2. Диаграмма рассеяния за 2022 год
data_2022 = final_df[final_df["year"] == 2022]
plt.figure(figsize=(10, 6))
plt.scatter(data_2022["urban_population_share"], data_2022["total_fertility_rate"], alpha=0.6)
plt.xlabel("Доля городского населения (%)")
plt.ylabel("Коэффициент рождаемости")
plt.title("Связь урбанизации и рождаемости по странам, 2022 г.")
for idx, row in data_2022.dropna().iterrows():
    plt.annotate(row["country"], (row["urban_population_share"], row["total_fertility_rate"]),
                 fontsize=8, alpha=0.7)
plt.tight_layout()
plt.show()

# 3. Тепловая карта изменений (2010 vs 2022)
df_heatmap = df_change.set_index("country")
df_heatmap = df_heatmap[["urbanization_change", "fertility_change"]].dropna()
plt.figure(figsize=(8, 10))
plt.imshow(df_heatmap.T, cmap="RdYlGn", aspect='auto', interpolation='none')
plt.colorbar(label="Изменение")
plt.xticks(np.arange(len(df_heatmap)), df_heatmap.index, rotation=90)
plt.yticks([0, 1], ["Δ Урбанизация", "Δ Рождаемость"])
plt.title("Изменение показателей по странам (2010–2022)")
for i in range(len(df_heatmap)):
    for j in range(2):
        text = plt.text(i, j, f"{df_heatmap.iloc[i, j]:.2f}",
                        ha="center", va="center", color="black", fontsize=6)
plt.tight_layout()
plt.show()

# 4. Глобальные карты (условно — без basemap, просто пример структуры)
# Имитация choropleth через bar plot по регионам (т.к. нет геометрии)
# В реальности требует geopandas и shape-файлы, но здесь ограничимся простым графиком

regions = {
    "RUS": "Russia", "USA": "United States", "CHN": "China", "IND": "India", "BRA": "Brazil",
    "NGA": "Nigeria", "DEU": "Germany", "JPN": "Japan", "ZAF": "South Africa", "AUS": "Australia"
}
data_2022_regional = data_2022[data_2022["country"].isin(regions.keys())].copy()
data_2022_regional["country_name"] = data_2022_regional["country"].map(regions)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
ax1.bar(data_2022_regional["country_name"], data_2022_regional["urban_population_share"], color='skyblue')
ax1.set_title("Доля городского населения, 2022")
ax1.set_ylabel("Процент")
ax1.tick_params(axis='x', rotation=45)

ax2.bar(data_2022_regional["country_name"], data_2022_regional["total_fertility_rate"], color='salmon')
ax2.set_title("Коэффициент рождаемости, 2022")
ax2.set_ylabel("Рождений на женщину")
ax2.tick_params(axis='x', rotation=45)

plt.tight_layout()
plt.show()

# === СОХРАНЕНИЕ ИТОГОВОГО ДАТАСЕТА ===
csv_path, meta_path = save_dataset_with_metadata(
    df=final_df,
    output_dir=OUTPUT_DIR,
    metadata={
        "query": "Динамика доли городского населения и общего коэффициента рождаемости по странам мира за 2010–2022. Источник: World Bank.",
        "sources": ["wb_sp_urb_totl_in_zs", "wb_sp_dyn_tfrt_in"],
        "indicators": ["urban_population_share", "total_fertility_rate"],
        "derived_metrics": [
            "urbanization_fertility_change_2010_2022",
            "correlation_urban_fertility_annual"
        ],
        "years": list(range(2010, 2023))
    },
    filename="output_dataset"
)
print(f"saved: {csv_path}")