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
    calculate_per_capita,
    save_dataset_with_metadata,
)

# Параметры
ARCHIVE_ROOT = r"D:\data"
OUTPUT_DIR = Path(r"outputs\20260511_122847")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === Загрузка данных ===
# Основной источник: доля городского населения
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

# Удаляем дубликаты по (country, year)
df_urban = df_urban.drop_duplicates(subset=["country", "year"], keep="first")

# Загружаем данные по общему коэффициенту рождаемости
file_path_fert = "wb/parquet/SP.DYN.TFRT.IN.parquet"
df_fert = read_wb_parquet(
    path=Path(ARCHIVE_ROOT) / file_path_fert,
    countryiso3=None,
    years=[2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022]
)

df_fert['source'] = 'wb_sp_dyn_tfrt_in'
df_fert['extraction_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

df_fert = rename_value_column(df_fert, "total_fertility_rate")
df_fert = df_fert.drop_duplicates(subset=["country", "year"], keep="first")

# === Объединение данных по стране и году ===
df_combined = join_on_country_year(df_urban, df_fert, country_col="country")

# Переименовываем country в countryiso3
df_combined = df_combined.rename(columns={"country": "countryiso3"})

# Фильтрация по годам (уже отфильтровано при чтении, но на всякий случай)
df_combined = filter_years(df_combined, [2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022])

# === Производные метрики ===

# 1. Изменение показателей за период 2010–2022
# Фильтруем данные за 2010 и 2022
df_2010 = df_combined[df_combined["year"] == 2010][["countryiso3", "urban_population_share", "total_fertility_rate"]]
df_2010 = df_2010.rename(columns={
    "urban_population_share": "urban_population_share_2010",
    "total_fertility_rate": "total_fertility_rate_2010"
})

df_2022 = df_combined[df_combined["year"] == 2022][["countryiso3", "urban_population_share", "total_fertility_rate"]]
df_2022 = df_2022.rename(columns={
    "urban_population_share": "urban_population_share_2022",
    "total_fertility_rate": "total_fertility_rate_2022"
})

df_change = pd.merge(df_2010, df_2022, on="countryiso3", how="inner")

# Рассчитываем изменение
df_change["urbanization_fertility_change_2010_2022_urban"] = \
    df_change["urban_population_share_2022"] - df_change["urban_population_share_2010"]

df_change["urbanization_fertility_change_2010_2022_fert"] = \
    df_change["total_fertility_rate_2022"] - df_change["total_fertility_rate_2010"]

# Добавляем метрику изменения в основной датафрейм через merge
df_combined = df_combined.merge(
    df_change[["countryiso3", "urbanization_fertility_change_2010_2022_urban", "urbanization_fertility_change_2010_2022_fert"]],
    on="countryiso3",
    how="left"
)

# 2. Отношение доли городского населения к коэффициенту рождаемости
df_combined["urbanization_fertility_ratio"] = np.where(
    df_combined["total_fertility_rate"] > 0,
    df_combined["urban_population_share"] / df_combined["total_fertility_rate"],
    np.nan
)

# === Визуализации ===

# 1. Линейный график динамики по отдельным крупным странам
countries_top = df_combined.groupby("countryiso3")["urban_population_share"].mean().nlargest(5).index
df_top = df_combined[df_combined["countryiso3"].isin(countries_top)]

plt.figure(figsize=(12, 6))
for country in countries_top:
    data = df_top[df_top["countryiso3"] == country]
    plt.plot(data["year"], data["urban_population_share"], label=f"{country} (урбанизация)")
    plt.plot(data["year"], data["total_fertility_rate"], linestyle="--", alpha=0.7,
             label=f"{country} (рождаемость)")

plt.title("Динамика урбанизации и коэффициента рождаемости по странам (2010–2022)")
plt.xlabel("Год")
plt.ylabel("Значение")
plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "plot_1.png", dpi=100, bbox_inches="tight")
plt.close()

# 2. Диаграмма рассеяния за 2022 год
df_2022_scatter = df_combined[df_combined["year"] == 2022].copy()
plt.figure(figsize=(10, 6))
plt.scatter(df_2022_scatter["urban_population_share"], df_2022_scatter["total_fertility_rate"], alpha=0.6)

# Трендовая линия
z = np.polyfit(df_2022_scatter["urban_population_share"].dropna(),
               df_2022_scatter["total_fertility_rate"].dropna(), 1)
p = np.poly1d(z)
plt.plot(df_2022_scatter["urban_population_share"], p(df_2022_scatter["urban_population_share"]), "r--", alpha=0.8)

plt.title("Соотношение урбанизации и коэффициента рождаемости, 2022 г.")
plt.xlabel("Доля городского населения (%)")
plt.ylabel("Коэффициент рождаемости (на женщину)")
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "plot_2.png", dpi=100, bbox_inches="tight")
plt.close()

# 3. Тепловая карта изменений по странам (2010 vs 2022)
df_heatmap = df_change.set_index("countryiso3")[
    ["urbanization_fertility_change_2010_2022_urban", "urbanization_fertility_change_2010_2022_fert"]
].dropna()

plt.figure(figsize=(8, 10))
plt.imshow(df_heatmap.T, cmap="RdYlGn", aspect="auto", interpolation="none")
plt.colorbar(label="Изменение показателя")
plt.xticks(np.arange(len(df_heatmap)), df_heatmap.index, rotation=90)
plt.yticks([0, 1], ["Изм. урбанизации", "Изм. рождаемости"])
plt.title("Изменение показателей по странам (2010–2022)")
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "plot_3.png", dpi=100, bbox_inches="tight")
plt.close()

# 4. Группированные столбчатые диаграммы по группам дохода (выделим вручную по среднему уровню дохода)
# Используем данные WB: группа стран по доходу (можно выделить по среднему значению urban_population_share или fertility)
# Временно: разобьем страны на 3 группы по уровню урбанизации в 2022
df_2022_group = df_combined[df_combined["year"] == 2022].copy()
df_2022_group = df_2022_group.dropna(subset=["urban_population_share", "total_fertility_rate"])

# Квантили по урбанизации
df_2022_group["urban_group"] = pd.qcut(df_2022_group["urban_population_share"], 3,
                                       labels=["Низкая урбанизация", "Средняя", "Высокая"])

grouped = df_2022_group.groupby("urban_group")[["urban_population_share", "total_fertility_rate"]].mean()

grouped.T.plot(kind="bar", figsize=(10, 6))
plt.title("Средние показатели по группам стран (по уровню урбанизации, 2022)")
plt.ylabel("Значение")
plt.xlabel("Группа стран")
plt.xticks(rotation=0)
plt.legend(title="Показатель")
plt.grid(True, axis='y', alpha=0.3)
plt.tight_layout()
plt.savefig(OUTPUT_DIR / "plot_4.png", dpi=100, bbox_inches="tight")
plt.close()

# === Формирование итогового датасета ===
final_df = df_combined[[
    "year",
    "countryiso3",
    "urban_population_share",
    "total_fertility_rate",
    "urbanization_fertility_ratio",
    "urbanization_fertility_change_2010_2022_urban",
    "urbanization_fertility_change_2010_2022_fert",
    "source",
    "extraction_date"
]].copy()

# Переименовываем столбцы под план
final_df = final_df.rename(columns={
    "urbanization_fertility_change_2010_2022_urban": "urbanization_fertility_change_2010_2022"
})

# Убираем total_fertility_rate из output_columns, если не требуется, но по описанию визуализации он нужен
# Оставляем как часть датасета

# Сохранение результата
csv_path, meta_path = save_dataset_with_metadata(
    df=final_df,
    output_dir=OUTPUT_DIR,
    metadata={
        "query": "Динамика доли городского населения и общего коэффициента рождаемости по странам мира за 2010–2022. Источник: World Bank.",
        "sources": ["wb_sp_urb_totl_in_zs", "wb_sp_dyn_tfrt_in"],
        "indicators": ["urban_population_share", "total_fertility_rate", "urbanization_fertility_ratio", "urbanization_fertility_change_2010_2022"]
    },
    filename="output_dataset"
)

print(f"saved: {csv_path}")