from pydantic import BaseModel

class DatasetEntry(BaseModel):
    """запись в реестре (наша база данных)"""
    id: str
    title: str
    description: str
    source: str # источник (например, world bank)
    geography: str # брикс, рф и т.д.
    period: str # 2015-2024
    columns: list[str] # список колонок в файле
    file_path: str # путь к parquet или csv файлу
    tags: list[str] # теги для поиска