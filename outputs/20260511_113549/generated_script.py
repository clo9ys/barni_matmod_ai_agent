```python
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
    calculate_index_to_base,
    save_dataset_with_metadata
)

# Параметры
ARCHIVE_ROOT = r"D:\data"
OUTPUT_DIR = Path(r"outputs\20260511_113549")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === ЗАГРУЗКА ДАННЫХ ===
# Загружаем долю городского населения (SP.URB.TOTL.IN.ZS)
file_path_urban = "wb/parquet/SP.URB.TOTL.IN.ZS.parquet"
df_urban = read_wb_parquet(
    path=Path(ARCHIVE_ROOT) / file_path_urban,
    countryiso3=None,
    years=[2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
)
df_urban = rename_value_column(df_urban, "urban_population_share")
df_urban['source'] = 'wb_sp_urb_totl_in_zs'
df_urban['extraction_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Загружаем общий коэффициент рождаемости (SP.DYN.TFRT.IN)
file_path_fertility = "wb/parquet/SP.DYN.TFRT.IN.parquet"
df_fertility = read_wb_parquet(
    path=Path(ARCHIVE_ROOT) / file_path_fertility,
    countryiso3=None,
    years=[2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
)
df_fertility = rename_value_column(df_fertility, "total_fertility_rate")
df_fertility['source'] = 'wb_sp_dyn_tfrt_in'
df_fertility['extraction_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# === ОБЪЕДИНЕНИЕ ДАННЫХ ПО СТРАНАМ И ГОДАМ ===
df_combined = pd.merge(df_urban, df_fertility, on=['country', 'country_name', 'year'], how='inner')

# Убедимся, что года в нужном диапазоне
df_combined = filter_years(df_combined, [2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022])

# === РАСЧЁТ ПРОИЗВОДНЫХ МЕТРИК ===
# Сортируем по стране и году
df_combined = df_combined.sort_values(by=['country', 'year'])

# Ежегодное изменение урбанизации
df_combined['annual_change_urbanization'] = df_combined.groupby('country')['urban_population_share'].diff()

# Ежегодное изменение рождаемости
df_combined['annual_change_fertility'] = df_combined.groupby('country')['total_fertility_rate'].diff()

# === ВИЗУАЛИЗАЦИИ ===

# 1. Линейный график динамики по странам (панельные данные)
top_countries = df_combined.groupby('country')['urban_population_share'].mean().nlargest(10).index
df_top = df_combined[df_combined['country'].isin(top_countries)]

fig, ax1 = plt.subplots(figsize=(12, 6))
for country in top_countries:
    data = df_top[df_top['country'] == country]
    ax1.plot(data['year'], data['urban_population_share'], label=f'{country} (urban)', alpha=0.7, linewidth=1)
ax1.set_xlabel('Год')
ax1.set_ylabel('Доля городского населения (%)', color='tab:blue')
ax1.tick_params(axis='y', labelcolor='tab:blue')
ax1.set_title('Динамика доли городского населения и коэффициента рождаемости (Топ-10 стран)')

ax2 = ax1.twinx()
for country in top_countries:
    data = df_top[df_top['country'] == country]
    ax2.plot(data['year'], data['total_fertility_rate'], linestyle='--', alpha=0.7, linewidth=1)
ax2.set_ylabel('Коэффициент рождаемости (рождений на женщину)', color='tab:orange')
ax2.tick_params(axis='y', labelcolor='tab:orange')

plt.title('Динамика урбанизации и рождаемости по странам')
plt.tight_layout()

# 2. Диаграмма рассеяния с трендовой линией (по всем годам и странам)
plt.figure(figsize=(10, 6))
plt.scatter(df_combined['urban_population_share'], df_combined['total_fertility_rate'], alpha=0.6)
z = np.polyfit(df_combined['urban_population_share'], df_combined['total_fertility_rate'], 1)
p = np.poly1d(z)
plt.plot(df_combined['urban_population_share'], p(df_combined['urban_population_share']), "r--", alpha=0.8, linewidth=2)
plt.xlabel('Доля городского населения (%)')
plt.ylabel('Коэффициент рождаемости (рождений на женщину)')
plt.title('Связь урбанизации и рождаемости (по странам, 2010–2022)')
plt.grid(True, alpha=0.3)

# 3. Тепловая карта изменений по странам и годам
# Берём среднее изменение по странам за год
pivot_change_urban = df_combined.pivot_table(index='country', columns='year', values='annual_change_urbanization')
plt.figure(figsize=(12, 8))
plt.imshow(pivot_change_urban, aspect='auto', cmap='RdYlGn', interpolation='none')
plt.colorbar(label='Изменение доли городского населения (%)')
plt.xticks(np.arange(len(pivot_change_urban.columns)), pivot_change_urban.columns.astype(int), rotation=45)
plt.yticks(np.arange(min(20, len(pivot_change_urban))), pivot_change_urban.index[:20])
plt.title('Тепловая карта ежегодного изменения урбанизации по странам')
plt.xlabel('Год')
plt.ylabel('Страна (первые 20)')

# 4. Групповые столбчатые диаграммы по регионам (пример для 2022 года)
# Для этого нужно добавить регионы — временно используем маппинг по странам (упрощённо)
region_mapping = {
    'USA': 'North America', 'CAN': 'North America', 'MEX': 'North America',
    'BRA': 'Latin America', 'ARG': 'Latin America', 'CHL': 'Latin America',
    'CHN': 'East Asia', 'JPN': 'East Asia', 'KOR': 'East Asia',
    'IND': 'South Asia', 'PAK': 'South Asia', 'BGD': 'South Asia',
    'RUS': 'Europe & Central Asia', 'DEU': 'Europe & Central Asia', 'FRA': 'Europe & Central Asia',
    'ZAF': 'Sub-Saharan Africa', 'NGA': 'Sub-Saharan Africa', 'EGY': 'Middle East & North Africa',
    'SAU': 'Middle East & North Africa', 'TUR': 'Middle East & North Africa'
}

df_combined['iso3'] = df_combined['country']
df_combined['region'] = df_combined['iso3'].map(region_mapping).fillna('Other')

data_2022 = df_combined[df_combined['year'] == 2022].dropna(subset=['region'])
avg_by_region = data_2022.groupby('region')[['urban_population_share', 'total_fertility_rate']].mean()

avg_by_region.plot(kind='bar', figsize=(12, 7), alpha=0.8)
plt.title('Средние показатели по регионам (2022)')
plt.ylabel('Значение')
plt.xlabel('Регион')
plt.xticks(rotation=45)
plt.legend(['Доля городского населения (%)', 'Коэффициент рождаемости'])
plt.grid(True, axis='y', alpha=0.3)

# === ФОРМИРОВАНИЕ ИТОГОВОГО ДАТАСЕТА ===
final_columns = ['year', 'urban_population_share', 'total_fertility_rate',
                 'annual_change_urbanization', 'annual_change_fertility']
final_df = df_combined[['country', 'country_name', 'year',
                        'urban_population_share', 'total_fertility_rate',
                        'annual_change_urbanization', 'annual_change_fertility']].copy()

# Расчёт корреляции по странам за период
correlations = []
for country, group in df_combined.groupby('country'):
    if len(group) > 5:
        corr = group[['urban_population_share', 'total_fertility_rate']].corr().iloc[0, 1]
        if not pd.isna(corr):
            correlations.append({'country': country, 'correlation_urbanization_fertility': corr})

df_corr = pd.DataFrame(correlations)
final_df = final_df.merge(df_corr, on='country', how='left')

# Добавим метаданные
csv_path, meta_path = save_dataset_with_metadata(
    df=final_df,
    output_dir=OUTPUT_DIR,
    metadata={
        "query": "Динамика доли городского населения и общего коэффициента рождаемости по странам мира за 2010–2022. Источник: World Bank.",
        "sources": ["wb_sp_urb_totl_in_zs", "wb_sp_dyn_tfrt_in"],
        "indicators": ["urban_population_share", "total_fertility_rate"],
        "combination_strategy": "single_source_with_secondary_join",
        "years_used": [2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022],
        "derived_metrics": [
            "annual_change_urbanization",
            "annual_change_fertility",
            "correlation_urbanization_fertility"
        ]
    },
    filename="output_dataset"
)

print(f"saved: {csv_path}")

plt.tight_layout()
plt.show()
```