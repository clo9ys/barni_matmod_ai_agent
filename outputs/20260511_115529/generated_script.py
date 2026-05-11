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
    save_dataset_with_metadata
)

# Параметры
ARCHIVE_ROOT = r"D:\data"
OUTPUT_DIR = Path(r"outputs\20260511_115529")
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

# Загрузка второго показателя: общий коэффициент рождаемости (World Bank)
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
df = pd.merge(df_urban, df_fertility, on=['country', 'year'], how='inner')

# Убедимся, что года в нужном диапазоне
df = filter_years(df, [2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022])

# === Расчет производных метрик ===
# Сортировка по стране и году
df = df.sort_values(by=['country', 'year']).reset_index(drop=True)

# Ежегодное изменение доли городского населения
df['annual_change_urbanization'] = df.groupby('country')['urban_population_share'].diff()

# Ежегодное изменение коэффициента рождаемости
df['annual_change_fertility'] = df.groupby('country')['total_fertility_rate'].diff()

# === Формирование итогового датасета ===
final_df = df[[
    'year', 'urban_population_share', 'total_fertility_rate',
    'annual_change_urbanization', 'annual_change_fertility', 'country'
]].copy()

# Убираем строки, где нет данных по обоим показателям
final_df = final_df.dropna(subset=['urban_population_share', 'total_fertility_rate']).reset_index(drop=True)

# === Визуализации ===

# 1. Линейный график динамики по странам (панельные данные — выбор ТОП-10 стран по населению)
top_countries = df[df['year'] == 2020].sort_values('urban_population_share', ascending=False).head(10)['country']
df_top = df[df['country'].isin(top_countries)]

fig, ax1 = plt.subplots(figsize=(14, 8))

for country in df_top['country'].unique():
    data = df_top[df_top['country'] == country]
    ax1.plot(data['year'], data['urban_population_share'], label=f'{country} (urban)', alpha=0.7, linewidth=1.2)
ax1.set_xlabel('Год')
ax1.set_ylabel('Доля городского населения (%)', color='tab:blue')
ax1.tick_params(axis='y', labelcolor='tab:blue')
ax1.grid(True, alpha=0.3)

ax2 = ax1.twinx()
for country in df_top['country'].unique():
    data = df_top[df_top['country'] == country]
    ax2.plot(data['year'], data['total_fertility_rate'], linestyle='--', alpha=0.6, linewidth=1)
ax2.set_ylabel('Общий коэффициент рождаемости (рождений на женщину)', color='tab:red')
ax2.tick_params(axis='y', labelcolor='tab:red')

plt.title('Динамика доли городского населения и коэффициента рождаемости (Топ-10 стран)')
fig.legend(loc="upper left", bbox_to_anchor=(0.1, 0.9))
plt.tight_layout()

# 2. Диаграмма рассеяния (по последнему году)
df_last = df[df['year'] == 2022].dropna(subset=['urban_population_share', 'total_fertility_rate'])
plt.figure(figsize=(10, 6))
plt.scatter(df_last['urban_population_share'], df_last['total_fertility_rate'], alpha=0.6)
z = np.polyfit(df_last['urban_population_share'], df_last['total_fertility_rate'], 1)
p = np.poly1d(z)
plt.plot(df_last['urban_population_share'], p(df_last['urban_population_share']), "r--", alpha=0.8, linewidth=1.5)
plt.xlabel('Доля городского населения (%)')
plt.ylabel('Общий коэффициент рождаемости (рождений на женщину)')
plt.title('Связь урбанизации и рождаемости (2022 г.)')
plt.grid(True, alpha=0.3)
plt.tight_layout()

# 3. Тепловая карта изменений по странам и годам (пример: annual_change_urbanization)
df_pivot = df.pivot(index='country', columns='year', values='annual_change_urbanization')
plt.figure(figsize=(12, 8))
plt.imshow(df_pivot, aspect='auto', cmap='RdYlGn', interpolation='none')
plt.colorbar(label='Изменение урбанизации (%)')
plt.yticks(range(len(df_pivot.index)), df_pivot.index)
plt.xticks(range(len(df_pivot.columns)), df_pivot.columns.astype(int), rotation=45)
plt.title('Тепловая карта ежегодного изменения доли городского населения')
plt.tight_layout()

# === Сохранение итогового датасета ===
csv_path, meta_path = save_dataset_with_metadata(
    df=final_df,
    output_dir=OUTPUT_DIR,
    metadata={
        "query": "Динамика доли городского населения и общего коэффициента рождаемости по странам мира за 2010–2022. Источник: World Bank.",
        "sources": ["wb_sp_urb_totl_in_zs", "wb_sp_dyn_tfrt_in"],
        "indicators": ["urban_population_share", "total_fertility_rate", "annual_change_urbanization", "annual_change_fertility"],
        "years": [2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
    },
    filename="output_dataset"
)
print(f"saved: {csv_path}")

plt.show()