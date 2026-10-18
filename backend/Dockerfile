# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN groupadd --system app && useradd --system --gid app --home-dir /app app
WORKDIR /app
COPY requirements.txt constraints.txt ./
RUN pip install -r requirements.txt -c constraints.txt

# ---- API / generic worker (no conversion engines) -------------------------------------
FROM base AS dev
COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt -c constraints.txt
COPY . .
RUN mkdir -p /data/storage && chown -R app:app /data
USER app

FROM base AS runtime
COPY . .
RUN mkdir -p /data/storage && chown -R app:app /data
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---- worker-light: documents + images ------------------------------------------------
# Debian 13 packages verified in Phase 1 (docs/architecture/07). No ImageMagick, no Pandoc.
FROM base AS worker-light
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libreoffice-writer-nogui libreoffice-calc-nogui \
      poppler-utils libvips-tools librsvg2-bin \
      libheif-plugin-libde265 libheif-plugin-aomenc libheif-plugin-dav1d \
      fonts-dejavu-core fonts-liberation \
 && rm -rf /var/lib/apt/lists/*
COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt -c constraints.txt
COPY . .
RUN mkdir -p /data/storage && chown -R app:app /data
USER app
CMD ["celery", "-A", "app.workers.celery_app", "worker", "-Q", "light", "--loglevel=INFO", "--concurrency=2"]

# ---- worker-media: audio + video ------------------------------------------------------
FROM base AS worker-media
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*
COPY requirements-dev.txt ./
RUN pip install -r requirements-dev.txt -c constraints.txt
COPY . .
RUN mkdir -p /data/storage && chown -R app:app /data
USER app
CMD ["celery", "-A", "app.workers.celery_app", "worker", "-Q", "media", "--loglevel=INFO", "--concurrency=1"]
