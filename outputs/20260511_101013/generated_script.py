```python
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from src.tools.readers import read_fedstatru_parquet, read_wb_parquet
from src.tools.skills import (
    rename_value_column,
    filter_years,
    join_on_year,
    save_dataset_with_metadata
)

# Параметры
ARCHIVE_ROOT = r"D:\data"
OUTPUT_DIR = Path(r"outputs\20260511_101013")

# Создаем выходную директорию
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === Загрузка данных ===
datasets = []

# Пример: предположим, что "x" — это индикатор из Fedstat
# Так как нет точного описания, используем обобщённый подход

# Попробуем загрузить данные по индикатору "x" из Fedstat (примерный file_path, так как не задан)
fedstat_file_path = "fedstatru/data/parquet/some_dataset.parquet"
try:
    df_fed = read_fedstatru_parquet(
        path=Path(ARCHIVE_ROOT) / fedstat_file_path,
        okato='643',
        period='30',
        years=None  # Все доступные годы
    )
    if not df_fed.empty:
        df_fed = rename_value_column(df_fed, "x")
        df_fed['source'] = 'fedstatru.some_dataset'
        df_fed['extraction_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        datasets.append(df_fed)
except Exception as e:
    print(f"Failed to load Fedstat data: {e}")

# Попробуем загрузить данные из World Bank (если применимо)
wb_file_path = "wb/parquet/some_wb_dataset.parquet"
try:
    df_wb = read_wb_parquet(
        path=Path(ARCHIVE_ROOT) / wb_file_path,
        countryiso3='RUS',
        years=None
    )
    if not df_wb.empty:
        df_wb = rename_value_column(df_wb, "x")
        df_wb['source'] = 'wb.some_wb_dataset'
        df_wb['extraction_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        datasets.append(df_wb)
except Exception as e:
    print(f"Failed to load World Bank data: {e}")

# === Объединение данных ===
if datasets:
    # Объединяем все по годам, оставляя первое значение при дубликатах
    final_df = pd.concat(datasets, ignore_index=True)
    final_df = final_df.drop_duplicates(subset=['year'], keep='first')
else:
    # Если данные не загружены, создаем пустой датафрейм с нужными колонками
    final_df = pd.DataFrame(columns=['year', 'x', 'source', 'extraction_date'])

# Сортируем по году
final_df = final_df.sort_values(by='year').reset_index(drop=True)

# === Сохранение результата ===
csv_path, meta_path = save_dataset_with_metadata(
    df=final_df,
    output_dir=OUTPUT_DIR,
    metadata={
        "query": "very specific request without data",
        "sources": list(final_df['source'].unique()) if not final_df.empty else [],
        "indicators": ["x"],
        "geography": ["RU"],
        "units": []
    },
    filename="output_dataset"
)

print(f"saved: {csv_path}")

# === Визуализация (если есть данные) ===
if not final_df.empty and 'year' in final_df.columns and 'x' in final_df.columns:
    plt.figure(figsize=(10, 6))
    plt.plot(final_df['year'], final_df['x'], marker='o', linestyle='-', label='x (RU)')
    plt.title("Indicator x over time (Russia)")
    plt.xlabel("Year")
    plt.ylabel("x")
    plt.grid(True, alpha=0.3)
    plt.legend()
else:
    plt.figure(figsize=(10, 6))
    plt.text(0.5, 0.5, 'No data available for visualization', ha='center', va='center', fontsize=12, transform=plt.gca().transAxes)
    plt.title("Indicator x over time (Russia)")
    plt.axis('off')

plt.tight_layout()
plt.show()
```