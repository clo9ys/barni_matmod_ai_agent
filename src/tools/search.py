import json
from src.core.registry import DatasetEntry
from src.core.state import DataSource


def load_registry(path: str = "data/registry.json") -> list[DatasetEntry]:
    # загрузка всех доступных датасетов
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [DatasetEntry(**item) for item in data]
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def find_datasets(query: str, registry: list[DatasetEntry]) -> list[DataSource]:
    # простейший поиск по ключевым словам
    # в будущем тут мл-инженер прикрутит faiss
    query = query.lower()
    results = []

    for entry in registry:
        if query in entry.title.lower() or query in entry.description.lower() or any(query in t for t in entry.tags):
            # конвертируем DatasetEntry (из базы) в DataSource (для стейта)
            results.append(DataSource(
                id=entry.id,
                title=entry.title,
                source_url=entry.file_path,  # для мвп путь к файлу будет как url
                relevance_score=1.0,
                description=entry.description
            ))
    return results