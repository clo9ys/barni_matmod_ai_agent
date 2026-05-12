# Этап 1: Сборка фронтенда
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY src/interface/package*.json ./
RUN npm install
COPY src/interface/ ./
RUN npm run build

# Этап 2: Подготовка бэкенда
FROM python:3.12-slim
WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Установка uv для управления зависимостями
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Копируем файлы зависимостей
COPY pyproject.toml uv.lock ./

# Устанавливаем зависимости (без dev)
RUN uv sync --frozen --no-dev

# Копируем исходный код
COPY src ./src

# Копируем собранный фронтенд в папку dist, которую ищет backend
COPY --from=frontend-builder /app/frontend/dist ./dist

# Предварительная загрузка ML-моделей при сборке образа
RUN .venv/bin/python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
import torch.nn as nn; \
SentenceTransformer('intfloat/multilingual-e5-small'); \
CrossEncoder('BAAI/bge-reranker-v2-m3', default_activation_function=nn.Sigmoid())"

# Экспонируем порт
EXPOSE 8000

# Команда запуска
CMD [".venv/bin/python", "-m", "uvicorn", "src.interface.main:app", "--host", "0.0.0.0", "--port", "8000"]
