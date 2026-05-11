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
    calculate_per_capita,
    save_dataset_with_metadata,
)

# Параметры
ARCHIVE_ROOT = r"D:\data"
OUTPUT_DIR = Path(r"outputs\20260511_142841")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === ЗАГРУЗКА ДАННЫХ ===
# Используем World Bank данные: номинальный ВВП (NY.GDP.MKTP.CD) и население (SP.POP.TOTL)
gdp_file_path = "wb/parquet/NY.GDP.MKTP.CD.parquet"
pop_file_path = "wb/parquet/SP.POP.TOTL.parquet"

# Читаем ВВП в текущих долларах США
df_gdp = read_wb_parquet(
    path=Path(ARCHIVE_ROOT) / gdp_file_path,
    countryiso3='RUS',
    years=list(range(2010, 2024))
)
df_gdp['source'] = 'wb_NY.GDP.MKTP.CD'
df_gdp['extraction_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Читаем численность населения
df_pop = read_wb_parquet(
    path=Path(ARCHIVE_ROOT) / pop_file_path,
    countryiso3='RUS',
    years=list(range(2010, 2024))
)
df_pop['source'] = 'wb_SP.POP.TOTL'
df_pop['extraction_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Переименовываем колонки значений
df_gdp = rename_value_column(df_gdp, "gdp_usd")
df_pop = rename_value_column(df_pop, "population")

# Фильтрация по годам (на случай, если в данных больше)
df_gdp = filter_years(df_gdp, list(range(2010, 2024)))
df_pop = filter_years(df_pop, list(range(2010, 2024)))

# === ОБЪЕДИНЕНИЕ ДАННЫХ ===
# Объединяем по году
df_combined = join_on_year(df_gdp, df_pop, how="outer")

# === РАСЧЕТ ПРОИЗВОДНОЙ МЕТРИКИ ===
# Рассчитываем ВВП на душу населения
df_result = df_combined.copy()
df_result['gdp_per_capita_usd'] = df_result['gdp_usd'] / df_result['population']

# Выбираем только нужные колонки по плану
df_result = df_result[['year', 'gdp_per_capita_usd']].copy()
df_result = df_result.sort_values('year').reset_index(drop=True)

# === ВИЗУАЛИЗАЦИЯ ===
# Линейный график
plt.figure(figsize=(12, 6))
plt.plot(df_result['year'], df_result['gdp_per_capita_usd'], marker='o', linewidth=2, markersize=5)
plt.title("Динамика ВВП на душу населения в России (2010–2023)", fontsize=14, fontweight='bold')
plt.xlabel("Год", fontsize=12)
plt.ylabel("ВВП на душу населения, текущие USD", fontsize=12)
plt.grid(True, alpha=0.3)
plt.xticks(df_result['year'].astype(int))
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "plot_1.png", dpi=100, bbox_inches="tight")
plt.close()

# Таблица с ежегодными значениями (сохраняем как изображение)
fig, ax = plt.subplots(figsize=(10, len(df_result) * 0.4 + 1))
ax.axis('tight')
ax.axis('off')
table_data = df_result.round(2).values.tolist()
columns = ['Год', 'ВВП на душу населения, USD']
table = ax.table(cellText=table_data, colLabels=columns, cellLoc='center', loc='center')
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1, 2)
plt.title("Ежегодные значения ВВП на душу населения", pad=20, fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "plot_2.png", dpi=100, bbox_inches="tight")
plt.close()

# === СОХРАНЕНИЕ ИТОГОВОГО ДАТАСЕТА ===
csv_path, meta_path = save_dataset_with_metadata(
    df=df_result,
    output_dir=OUTPUT_DIR,
    metadata={
        "query": "Динамика ВВП России на душу населения за 2010-2023 годы",
        "sources": ["wb_NY.GDP.MKTP.CD", "wb_SP.POP.TOTL"],
        "indicators": ["gdp_per_capita_usd"],
        "description": "Номинальный ВВП на душу населения в текущих долларах США, рассчитанный как ВВП в USD / население"
    },
    filename="output_dataset"
)

print(f"saved: {csv_path}")