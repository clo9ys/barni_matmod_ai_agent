# Stage 1: Frontend build
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY src/interface/package*.json ./
RUN npm ci
COPY src/interface/ ./
RUN npm run build

# Stage 2: Backend
FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache

COPY . .
COPY --from=frontend-builder /build/dist ./dist

ENV ARCHIVE_ROOT=/app/data/archive

EXPOSE 8000
CMD ["uvicorn", "src.interface.main:app", "--host", "0.0.0.0", "--port", "8000"]
