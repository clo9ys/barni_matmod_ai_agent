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
OUTPUT_DIR = Path(r"outputs\20260511_122134")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === ЗАГРУЗКА ДАННЫХ ===
# Загрузка доли городского населения (в процентах)
file_path_urban = "wb/parquet/SP.URB.TOTL.IN.ZS.parquet"
df_urban = read_wb_parquet(
    path=Path(ARCHIVE_ROOT) / file_path_urban,
    countryiso3=None,
    years=[2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
)

# Добавляем метаданные
df_urban['source'] = 'wb_sp_urb_totl_in_zs'
df_urban['extraction_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Переименовываем value -> urban_population_share
df_urban = rename_value_column(df_urban, "urban_population_share")

# Фильтрация по годам (на случай, если в данных больше)
df_urban = filter_years(df_urban, [2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022])

# Удаляем дубликаты по стране и году
df_urban = df_urban.drop_duplicates(subset=["country", "year"], keep="first")

# === ЗАГРУЗКА ОБЩЕГО КОЭФФИЦИЕНТА РОЖДАЕМОСТИ ===
file_path_fert = "wb/parquet/SP.DYN.TFRT.IN.parquet"
df_fert = read_wb_parquet(
    path=Path(ARCHIVE_ROOT) / file_path_fert,
    countryiso3=None,
    years=[2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
)

df_fert['source'] = 'wb_sp_dyn_tfrt_in'
df_fert['extraction_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

df_fert = rename_value_column(df_fert, "total_fertility_rate")
df_fert = filter_years(df_fert, [2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022])

df_fert = df_fert.drop_duplicates(subset=["country", "year"], keep="first")

# === ОБЪЕДИНЕНИЕ ДАННЫХ ===
df_combined = join_on_country_year(df_urban, df_fert, country_col="country", how="inner")

# Убедимся, что типы корректны
df_combined["year"] = df_combined["year"].astype(int)

# === РАСЧЁТ ПРОИЗВОДНЫХ МЕТРИК ===
# Сортируем по стране и году
df_combined = df_combined.sort_values(by=["country", "year"])

# Рассчитываем изменения (дельты) по сравнению с предыдущим годом
df_combined["urban_change"] = df_combined.groupby("country")["urban_population_share"].diff()
df_combined["fertility_change"] = df_combined.groupby("country")["total_fertility_rate"].diff()

# Также можно рассчитать изменение с базового года (например, 2010)
df_base_2010 = df_combined[df_combined["year"] == 2010][["country", "urban_population_share", "total_fertility_rate"]].copy()
df_base_2010 = df_base_2010.rename(columns={
    "urban_population_share": "urban_2010",
    "total_fertility_rate": "fertility_2010"
})

df_final = pd.merge(df_combined, df_base_2010, on="country", how="left")

df_final["urban_vs_base"] = df_final["urban_population_share"] - df_final["urban_2010"]
df_final["fertility_vs_base"] = df_final["total_fertility_rate"] - df_final["fertility_2010"]

# Финальный датасет: оставляем только нужные колонки
final_df = df_final[[
    "country", "year", "urban_population_share", "total_fertility_rate",
    "urban_change", "fertility_change", "urban_vs_base", "fertility_vs_base"
]].copy()

# === ВИЗУАЛИЗАЦИИ ===

# 1. Линейный график динамики по отдельным странам (выберем топ-10 по населению или просто пример)
top_countries = final_df.groupby("country")["urban_population_share"].mean().sort_values(ascending=False).head(10).index
df_top = final_df[final_df["country"].isin(top_countries)]

fig, ax = plt.subplots(figsize=(12, 6))
for country in top_countries:
    data = df_top[df_top["country"] == country]
    ax.plot(data["year"], data["urban_population_share"], label=f"{country} (urban)", alpha=0.8, linewidth=1)
    ax.plot(data["year"], data["total_fertility_rate"], linestyle="--", alpha=0.7, linewidth=1)

ax.set_title("Динамика доли городского населения и коэффициента рождаемости (2010–2022)")
ax.set_xlabel("Год")
ax.set_ylabel("Значение")
ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
plt.xticks(df_top["year"].unique())
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

# 2. Scatter plot: urban_population_share vs total_fertility_rate
fig, ax = plt.subplots(figsize=(10, 6))
scatter = ax.scatter(
    df_final["urban_population_share"],
    df_final["total_fertility_rate"],
    c=df_final["year"],
    cmap="viridis",
    alpha=0.6,
    edgecolors="w",
    linewidth=0.5
)
plt.colorbar(scatter, ax=ax, label="Год")
z = np.polyfit(df_final["urban_population_share"], df_final["total_fertility_rate"], 1)
p = np.poly1d(z)
ax.plot(df_final["urban_population_share"], p(df_final["urban_population_share"]), "--", color="red", label="Тренд")
ax.set_title("Городское население vs Коэффициент рождаемости (все страны и годы)")
ax.set_xlabel("Доля городского населения (%)")
ax.set_ylabel("Коэффициент рождаемости (рождений на женщину)")
ax.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()

# 3. Тепловая карта изменений по странам (изменение с 2010 по 2022)
df_pivot_urban = df_final.pivot_table(index="country", columns="year", values="urban_population_share", aggfunc="first")
df_pivot_fert = df_final.pivot_table(index="country", columns="year", values="total_fertility_rate", aggfunc="first")

# Изменение за период
change_urban = df_pivot_urban[2022] - df_pivot_urban[2010]
change_fert = df_pivot_fert[2022] - df_pivot_fert[2010]

# Объединяем в один датафрейм
change_df = pd.DataFrame({
    "urban_change": change_urban,
    "fertility_change": change_fert
}).dropna()

# Берём топ-20 стран по изменению урбанизации
top_change = change_df.sort_values("urban_change", ascending=False).head(20)

fig, ax = plt.subplots(figsize=(10, 6))
im = ax.imshow(top_change.T, cmap="RdYlGn", aspect="auto", interpolation="nearest")
ax.set_xticks(np.arange(len(top_change)))
ax.set_xticklabels(top_change.index, rotation=45, ha="left")
ax.set_yticks([0, 1])
ax.set_yticklabels(["Δ Урбанизация", "Δ Рождаемость"])
plt.colorbar(im, ax=ax)
ax.set_title("Тепловая карта изменений (2010–2022), топ-20 стран")
plt.tight_layout()
plt.show()

# 4. Панельные графики по группам (пример: по континентам — если есть классификация)
# Временно: используем приближение — разобьём на квантили по уровню урбанизации в 2010
df_2010 = df_final[df_final["year"] == 2010].set_index("country")["urban_population_share"]
df_2010 = pd.cut(df_2010, bins=3, labels=["Low", "Medium", "High"])

fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
for i, group in enumerate(["Low", "Medium", "High"]):
    countries_in_group = df_2010[df_2010 == group].index
    data_group = df_final[df_final["country"].isin(countries_in_group)]
    if len(data_group) == 0:
        continue
    avg_urban = data_group.groupby("year")["urban_population_share"].mean()
    avg_fert = data_group.groupby("year")["total_fertility_rate"].mean()
    ax = axes[i]
    ax.plot(avg_urban.index, avg_urban.values, label="Urban Share", marker="o", markersize=4)
    ax.plot(avg_fert.index, avg_fert.values, label="Fertility Rate", marker="s", markersize=4)
    ax.set_title(f"Группа: {group} urbanization (2010)")
    ax.set_xlabel("Год")
    ax.grid(True, alpha=0.3)
    if i == 0:
        ax.set_ylabel("Среднее значение")
    ax.legend()

plt.suptitle("Панельные графики по группам стран (по уровню урбанизации в 2010)")
plt.tight_layout()
plt.show()

# === СОХРАНЕНИЕ ИТОГОВОГО ДАТАСЕТА ===
csv_path, meta_path = save_dataset_with_metadata(
    df=final_df,
    output_dir=OUTPUT_DIR,
    metadata={
        "query": "Динамика доли городского населения и общего коэффициента рождаемости по странам мира за 2010–2022",
        "sources": ["wb_sp_urb_totl_in_zs", "wb_sp_dyn_tfrt_in"],
        "indicators": ["urban_population_share", "total_fertility_rate"],
        "description": "Объединённый датасет из World Bank: урбанизация и рождаемость, 2010–2022, с расчётами изменений."
    },
    filename="urbanization_fertility_dataset"
)

print(f"saved: {csv_path}")