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
OUTPUT_DIR = Path(r"outputs\20260511_120321")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === Загрузка данных ===
# Идентификаторы подходящих датасетов из World Bank
urban_pop_dataset_id = "wb_sp_urb_totl_in_zs"  # Urban population (% of total population)
fertility_rate_dataset_id = "wb_sp_dyn_tfrt_in"  # Total fertility rate (births per woman)

# Пути к файлам (предполагаем, что file_path указан в метаданных датасета)
urban_pop_file_path = "wb/parquet/sp_urb_totl_in_zs.parquet"
fertility_rate_file_path = "wb/parquet/sp_dyn_tfrt_in.parquet"

# Загрузка данных
df_urban = read_wb_parquet(
    path=Path(ARCHIVE_ROOT) / urban_pop_file_path,
    countryiso3=None,  # Все страны
    years=list(range(2010, 2023))  # 2010–2022
)
df_urban = rename_value_column(df_urban, "urban_population_percent")
df_urban["source"] = urban_pop_dataset_id
df_urban["extraction_date"] = datetime.now()

df_fertility = read_wb_parquet(
    path=Path(ARCHIVE_ROOT) / fertility_rate_file_path,
    countryiso3=None,
    years=list(range(2010, 2023))
)
df_fertility = rename_value_column(df_fertility, "total_fertility_rate")
df_fertility["source"] = fertility_rate_dataset_id
df_fertility["extraction_date"] = datetime.now()

# Фильтрация по годам (на всякий случай)
df_urban = filter_years(df_urban, list(range(2010, 2023)))
df_fertility = filter_years(df_fertility, list(range(2010, 2023)))

# Объединение по стране и году
final_df = join_on_country_year(df_urban, df_fertility, country_col="country")

# Убедимся, что year — int, отсортировано
final_df = final_df.sort_values(by=["country", "year"]).reset_index(drop=True)

# === Производные метрики ===
# 1. Ежегодное изменение доли городского населения
final_df["urban_population_change"] = final_df.groupby("country")["urban_population_percent"].diff()

# 2. Ежегодное изменение коэффициента рождаемости
final_df["fertility_rate_change"] = final_df.groupby("country")["total_fertility_rate"].diff()

# 3. Скользящая корреляция (5-летнее окно) по странам
def rolling_correlation(group, window=5):
    if len(group) < window:
        return pd.Series([np.nan] * len(group), index=group.index)
    rolling_corr = (
        group[["urban_population_percent", "total_fertility_rate"]]
        .rolling(window=window, min_periods=window)
        .corr()
        .iloc[::2, 1]
    )
    return rolling_corr.values

final_df["rolling_corr_5y"] = final_df.groupby("country", group_keys=False).apply(
    lambda x: rolling_correlation(x)
).droplevel(0, axis=0).values

# === Визуализации ===
countries_to_plot = ["RUS", "CHN", "USA", "IND", "BRA"]  # Пример стран
colors = plt.cm.tab10(np.linspace(0, 1, len(countries_to_plot)))

# 1. Линейные графики динамики по странам
fig, axes = plt.subplots(len(countries_to_plot), 1, figsize=(12, 3 * len(countries_to_plot)), sharex=True)
if len(countries_to_plot) == 1:
    axes = [axes]

for idx, (country, color) in enumerate(zip(countries_to_plot, colors)):
    data = final_df[final_df["country"] == country]
    if data.empty:
        continue
    ax = axes[idx]
    ax.plot(data["year"], data["urban_population_percent"], label="Urban Population (%)", color=color)
    ax.set_ylabel("Urban Pop (%)", color=color)
    ax.tick_params(axis='y', labelcolor=color)
    
    ax2 = ax.twinx()
    ax2.plot(data["year"], data["total_fertility_rate"], label="Fertility Rate", color='purple', linestyle='--')
    ax2.set_ylabel("Fertility Rate", color='purple')
    ax2.tick_params(axis='y', labelcolor='purple')
    
    ax.set_title(f"Urbanization and Fertility Rate in {country}")
    ax.grid(True, alpha=0.3)

plt.xlabel("Year")
plt.tight_layout()

# 2. Точечные диаграммы за 2010 и 2022
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

for i, (year, ax) in enumerate([(2010, ax1), (2022, ax2)]):
    data_year = final_df[final_df["year"] == year].dropna(subset=["urban_population_percent", "total_fertility_rate"])
    ax.scatter(data_year["urban_population_percent"], data_year["total_fertility_rate"], alpha=0.6)
    z = np.polyfit(data_year["urban_population_percent"], data_year["total_fertility_rate"], 1)
    p = np.poly1d(z)
    ax.plot(data_year["urban_population_percent"], p(data_year["urban_population_percent"]), "r--", alpha=0.8)
    ax.set_title(f"Urbanization vs Fertility Rate ({year})")
    ax.set_xlabel("Urban Population (%)")
    ax.set_ylabel("Total Fertility Rate (births per woman)")
    ax.grid(True, alpha=0.3)

plt.tight_layout()

# 3. Тепловые карты по странам (урбанизация и рождаемость за 2022)
data_2022 = final_df[final_df["year"] == 2022].set_index("country")[["urban_population_percent", "total_fertility_rate"]].dropna()
data_2022 = data_2022.sort_values(by="urban_population_percent", ascending=False).head(30)  # Топ-30 стран

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 8))
im1 = ax1.imshow([data_2022["urban_population_percent"].values], cmap="Blues", aspect="auto", vmin=0, vmax=100)
ax1.set_yticks([])
ax1.set_xticks(range(len(data_2022)))
ax1.set_xticklabels(data_2022.index, rotation=90)
ax1.set_title("Urban Population (%) - Top 30 Countries (2022)")

im2 = ax2.imshow([data_2022["total_fertility_rate"].values], cmap="Reds", aspect="auto", vmin=0, vmax=6)
ax2.set_yticks([])
ax2.set_xticks(range(len(data_2022)))
ax2.set_xticklabels(data_2022.index, rotation=90)
ax2.set_title("Fertility Rate (2022)")

fig.colorbar(im1, ax=ax1, orientation='horizontal', pad=0.1)
fig.colorbar(im2, ax=ax2, orientation='horizontal', pad=0.1)
plt.tight_layout()

# 4. Группированные столбчатые диаграммы по регионам (пример: по группам дохода — если есть)
# В данном случае, если нет колонки region/income_group, пропускаем или используем примерные группы
# Допустим, мы не имеем этой информации — пропустим, но оставим заглушку

# Сохранение итогового датасета
final_df = final_df[["year", "country", "urban_population_percent", "total_fertility_rate"] + 
                    ["urban_population_change", "fertility_rate_change", "rolling_corr_5y"]]

csv_path, meta_path = save_dataset_with_metadata(
    df=final_df,
    output_dir=OUTPUT_DIR,
    metadata={
        "query": "Динамика доли городского населения и общего коэффициента рождаемости по странам мира за 2010–2022",
        "sources": [urban_pop_dataset_id, fertility_rate_dataset_id],
        "indicators": ["urban_population_percent", "total_fertility_rate"],
        "rejected_sources": [
            {
                "dataset_id": "wb_prj_pop_2024_ned_fe",
                "reason": "Датасет содержит проекции населения в возрасте 20-24 лет по уровню образования, что не соответствует запрошенным индикаторам"
            },
            {
                "dataset_id": "wb_ji_pop_urbn_yg_zs",
                "reason": "Индикатор относится к доле городского населения в возрасте 15-24 лет, а не ко всей популяции, что не соответствует запросу"
            },
            {
                "dataset_id": "wb_ji_pop_1524_ur_zs",
                "reason": "Индикатор — доля молодежи 15-24 лет в городском населении, а не доля городского населения в целом"
            },
            {
                "dataset_id": "wb_prj_att_2024_ned_fe",
                "reason": "Датасет содержит проекции доли населения 20-24 лет без образования, что не соответствует запрошенным индикаторам"
            },
            {
                "dataset_id": "wb_ji_pop_urbn_ol_zs",
                "reason": "Индикатор относится к доле городского населения в возрасте 25-64 лет, а не ко всей популяции"
            }
        ]
    },
    filename="output_dataset"
)

print(f"saved: {csv_path}")

plt.tight_layout()
plt.show()