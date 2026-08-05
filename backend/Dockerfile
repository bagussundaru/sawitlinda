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

# Torch DAN torchvision dipasang dari indeks CPU LEBIH DULU.
#
# torchvision wajib ikut disebut di sini: ultralytics menariknya, dan wheel
# torchvision dari PyPI membawa serta seluruh tumpukan CUDA. Terukur di image
# yang terlanjur dibangun: 2,7 GB pustaka nvidia + 691 MB triton, seluruhnya
# tak terpakai di VM tanpa GPU. Memasangnya lebih dulu membuat pip menganggap
# kebutuhan itu sudah terpenuhi saat ultralytics dipasang.
RUN pip install --no-cache-dir torch==2.13.0 torchvision \
        --index-url https://download.pytorch.org/whl/cpu

# Dev-only packages are dropped from the image.
#
# opencv-python ditukar dengan varian headless setelah pemasangan. Ultralytics
# menariknya sebagai `opencv-python`, yang menautkan pustaka X11 (libxcb, libGL)
# — pustaka itu tidak ada di image slim, dan akibatnya `import cv2` gagal saat
# inference dijalankan. Varian headless memakai nama modul yang sama, tidak
# butuh X11, dan lebih kecil.
RUN grep -viE '^(pytest|pgserver|pypdf)' requirements.txt > requirements.prod.txt \
    && pip install --no-cache-dir -r requirements.prod.txt \
    && pip uninstall -y opencv-python \
    && pip install --no-cache-dir opencv-python-headless

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
