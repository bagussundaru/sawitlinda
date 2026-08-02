# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# libpq is needed by psycopg at runtime; the rest of the build tooling is not kept.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Dev-only packages are dropped from the image.
RUN grep -viE '^(pytest|httpx|pgserver|pypdf)' requirements.txt > requirements.prod.txt \
    && pip install --no-cache-dir -r requirements.prod.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts

# Run as an unprivileged user; storage is a mounted volume it must own.
RUN useradd --create-home --uid 10001 sawitscan \
    && mkdir -p /app/storage \
    && chown -R sawitscan:sawitscan /app
USER sawitscan

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
