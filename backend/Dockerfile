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

# ---- worker-ai: background removal + inpainting (CPU, ONNX Runtime) ------------------
# Models are downloaded at BUILD time and pinned by SHA-256; the running worker has no internet.
FROM base AS ai-models
RUN python - <<'PY'
import hashlib, os, urllib.request
os.makedirs("/opt/models", exist_ok=True)
MODELS = {
    "isnet-general-use.onnx": ("https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx",
                               "60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a"),
    "lama_fp32.onnx": ("https://huggingface.co/Carve/LaMa-ONNX/resolve/main/lama_fp32.onnx",
                       "1faef5301d78db7dda502fe59966957ec4b79dd64e16f03ed96913c7a4eb68d6"),
}
for name, (url, sha) in MODELS.items():
    path = f"/opt/models/{name}"
    urllib.request.urlretrieve(url, path)
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if digest != sha:
        raise SystemExit(f"checksum mismatch for {name}: {digest}")
    print("ok", name)
PY

FROM base AS worker-ai
# libvips-tools only for the upload probe (header read) so the image can run the full test flow.
RUN apt-get update && apt-get install -y --no-install-recommends libvips-tools && rm -rf /var/lib/apt/lists/*
COPY requirements-ai.txt requirements-dev.txt ./
RUN pip install -r requirements-ai.txt -r requirements-dev.txt -c constraints.txt
COPY --from=ai-models /opt/models /opt/models
COPY . .
RUN mkdir -p /data/storage && chown -R app:app /data
ENV AI_MODEL_DIR=/opt/models AI_THREADS=2
USER app
CMD ["celery", "-A", "app.workers.celery_app", "worker", "-Q", "ai", "--loglevel=INFO", "--concurrency=1"]

# ---- worker-download: yt-dlp + FFmpeg. NO database, NO direct internet ----------------
# Its only network is `dlnet` (Redis + egress proxy). Every outbound request goes through the
# egress proxy, which enforces the SSRF rules per connection.
FROM base AS worker-download
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements-download.txt requirements-dev.txt ./
RUN pip install -r requirements-download.txt -r requirements-dev.txt -c constraints.txt
COPY . .
RUN mkdir -p /data/storage && chown -R app:app /data
USER app
CMD ["celery", "-A", "app.workers.celery_app", "worker", "-Q", "download", "--loglevel=INFO", "--concurrency=2"]
