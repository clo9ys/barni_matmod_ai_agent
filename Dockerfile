# syntax=docker/dockerfile:1

# Этап 1: Сборка фронтенда
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY src/interface/package*.json ./
RUN npm ci
COPY src/interface/ ./
RUN npm run build

# Этап 2: Бэкенд
FROM python:3.12-slim
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

COPY src ./src
COPY --from=frontend-builder /app/frontend/dist ./dist

# Предварительная загрузка ML-моделей (кэшируется между сборками)
RUN --mount=type=cache,target=/root/.cache/huggingface \
    .venv/bin/python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
import torch.nn as nn; \
SentenceTransformer('intfloat/multilingual-e5-small'); \
CrossEncoder('BAAI/bge-reranker-v2-m3', activation_fn=nn.Sigmoid())"

EXPOSE 8000

CMD [".venv/bin/python", "-m", "uvicorn", "src.interface.main:app", "--host", "0.0.0.0", "--port", "8000"]
