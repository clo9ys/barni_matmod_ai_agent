from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from src.tools.readers import read_wb_parquet
from src.tools.skills import (
    rename_value_column,
    filter_years,
    join_on_year,
    join_on_country_year,
    save_dataset_with_metadata
)

# Параметры
ARCHIVE_ROOT = r"D:\data"
OUTPUT_DIR = Path(r"outputs\20260511_120927")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === Загрузка данных ===
# Основной источник: доля городского населения
file_path_urban = "wb/parquet/SP.URB.TOTL.IN.ZS.parquet"
df_urban = read_wb_parquet(
    path=Path(ARCHIVE_ROOT) / file_path_urban,
    countryiso3=None,
    years=[2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
)
df_urban = rename_value_column(df_urban, "urban_population_share")
df_urban['source'] = 'wb_sp_urb_totl_in_zs'
df_urban['extraction_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Загрузка второго индикатора: общий коэффициент рождаемости (Total Fertility Rate)
# Идентификатор индикатора в World Bank: SP.DYN.TFRT.IN
file_path_fertility = "wb/parquet/SP.DYN.TFRT.IN.parquet"
df_fertility = read_wb_parquet(
    path=Path(ARCHIVE_ROOT) / file_path_fertility,
    countryiso3=None,
    years=[2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
)
df_fertility = rename_value_column(df_fertility, "total_fertility_rate")
df_fertility['source'] = 'wb_sp_dyn_tfrt_in'
df_fertility['extraction_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# === Объединение данных по стране и году ===
df_combined = join_on_country_year(df_urban, df_fertility, country_col="country")

# Убедимся, что года в нужном диапазоне
df_combined = filter_years(df_combined, [2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022])

# Сортировка по стране и году
df_combined = df_combined.sort_values(by=["country", "year"]).reset_index(drop=True)

# === Расчет производных метрик ===
# Ежегодное изменение урбанизации и рождаемости
df_combined['annual_change_urbanization'] = df_combined.groupby('country')['urban_population_share'].diff()
df_combined['annual_change_fertility'] = df_combined.groupby('country')['total_fertility_rate'].diff()

# Коэффициент корреляции Пирсона между урбанизацией и рождаемостью по странам
correlation_data = []
correlation_grouped = df_combined.dropna(subset=['urban_population_share', 'total_fertility_rate']).groupby('country').apply(
    lambda group: np.corrcoef(group['urban_population_share'], group['total_fertility_rate'])[0, 1] if len(group) > 1 else np.nan
)
correlation_df = correlation_grouped.reset_index()
correlation_df.columns = ['country', 'correlation_urbanization_fertility_by_country']

# Присоединяем коэффициент корреляции к основному датафрейму
df_final = df_combined.merge(correlation_df, on='country', how='left')

# Выбираем только требуемые колонки
output_columns = ['year', 'urban_population_share', 'total_fertility_rate']
df_output = df_final[['country'] + output_columns + [
    'annual_change_urbanization',
    'annual_change_fertility',
    'correlation_urbanization_fertility_by_country',
    'source',
    'extraction_date'
]].copy()

# === Визуализации ===

# 1. Панельные линейные графики по странам (выберем топ-10 по населению или просто несколько крупных)
top_countries = ['USA', 'CHN', 'IND', 'IDN', 'BRA', 'RUS', 'NGA', 'JPN', 'MEX', 'DEU']
fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(14, 10), sharex=True)

for country in top_countries:
    data = df_final[df_final['country'] == country]
    if data.empty:
        continue
    axes[0].plot(data['year'], data['urban_population_share'], label=country, alpha=0.7)
    axes[1].plot(data['year'], data['total_fertility_rate'], label=country, alpha=0.7)

axes[0].set_title("Динамика доли городского населения по странам (2010–2022)")
axes[0].set_ylabel("Urban Population Share (%)")
axes[0].grid(True, alpha=0.3)
axes[0].legend(ncol=2, fontsize='small')

axes[1].set_title("Динамика общего коэффициента рождаемости по странам (2010–2022)")
axes[1].set_ylabel("Total Fertility Rate (births per woman)")
axes[1].set_xlabel("Год")
axes[1].grid(True, alpha=0.3)
axes[1].legend(ncol=2, fontsize='small')

plt.tight_layout()
plt.show()

# 2. Диаграмма рассеяния с трендовой линией (по всем данным)
plt.figure(figsize=(10, 6))
plt.scatter(df_final['urban_population_share'], df_final['total_fertility_rate'], alpha=0.5, color='blue')
z = np.polyfit(df_final['urban_population_share'], df_final['total_fertility_rate'], 1)
p = np.poly1d(z)
plt.plot(df_final['urban_population_share'], p(df_final['urban_population_share']), "r--", alpha=0.8, label="Trend line")
plt.xlabel("Urban Population Share (%)")
plt.ylabel("Total Fertility Rate (births per woman)")
plt.title("Связь урбанизации и рождаемости (2010–2022)")
plt.grid(True, alpha=0.3)
plt.legend()
plt.tight_layout()
plt.show()

# 3. Тепловая карта изменений по странам (2010 vs 2022)
pivot_2010 = df_final[df_final['year'] == 2010].set_index('country')[['urban_population_share', 'total_fertility_rate']]
pivot_2022 = df_final[df_final['year'] == 2022].set_index('country')[['urban_population_share', 'total_fertility_rate']]

change_df = pivot_2022.subtract(pivot_2010, fill_value=np.nan)
change_df = change_df.rename(columns={
    'urban_population_share': 'urban_change_2010_2022',
    'total_fertility_rate': 'fertility_change_2010_2022'
})

# Удалим строки без данных
change_df = change_df.dropna(how='all')

# Тепловая карта
fig, ax = plt.subplots(figsize=(10, 8))
im = ax.imshow(change_df.T, cmap="RdYlGn", aspect='auto', vmin=-30, vmax=30)

# Оси
ax.set_xticks(np.arange(len(change_df)))
ax.set_yticks(np.arange(len(change_df.columns)))
ax.set_xticklabels(change_df.index, rotation=90)
ax.set_yticklabels(change_df.columns)

# Цветовая шкала
plt.colorbar(im, ax=ax)
plt.title("Изменение показателей по странам: 2010–2022")
plt.tight_layout()
plt.show()

# 4. График с двумя осями: средние значения по миру
world_avg = df_final.groupby('year')[['urban_population_share', 'total_fertility_rate']].mean().reset_index()

fig, ax1 = plt.subplots(figsize=(10, 6))

color = 'tab:blue'
ax1.set_xlabel('Год')
ax1.set_ylabel('Urban Population Share (%)', color=color)
ax1.plot(world_avg['year'], world_avg['urban_population_share'], color=color, marker='o', label='Urban Share')
ax1.tick_params(axis='y', labelcolor=color)
ax1.set_title("Средние значения по миру: урбанизация и рождаемость")

ax2 = ax1.twinx()
color = 'tab:red'
ax2.set_ylabel('Total Fertility Rate', color=color)
ax2.plot(world_avg['year'], world_avg['total_fertility_rate'], color=color, marker='s', label='Fertility Rate')
ax2.tick_params(axis='y', labelcolor=color)

fig.tight_layout()
plt.title("Динамика средних значений по миру (двойная ось)")
fig.legend(loc="upper right", bbox_to_anchor=(0.85, 0.85))
plt.tight_layout()
plt.show()

# === Сохранение результата ===
csv_path, meta_path = save_dataset_with_metadata(
    df=df_output,
    output_dir=OUTPUT_DIR,
    metadata={
        "query": "Динамика доли городского населения и общего коэффициента рождаемости по странам мира за 2010–2022",
        "sources": ["wb_sp_urb_totl_in_zs", "wb_sp_dyn_tfrt_in"],
        "indicators": ["urban_population_share", "total_fertility_rate"],
        "derived_metrics": [
            "annual_change_urbanization",
            "annual_change_fertility",
            "correlation_urbanization_fertility_by_country"
        ],
        "visualization_types": [
            "panel_line_plot",
            "scatter_with_trend",
            "heatmap_change_2010_2022",
            "dual_axis_world_avg"
        ]
    },
    filename="output_dataset"
)
print(f"saved: {csv_path}")