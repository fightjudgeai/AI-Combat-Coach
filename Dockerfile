# AI-Combat-Coach — vision pipeline
# CPU-only build; add --build-arg BASE=pytorch/pytorch:2.2.2-cuda12.1-cudnn8-runtime
# for GPU support.
ARG BASE=python:3.12-slim
FROM ${BASE}

# ── system deps ──────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps ──────────────────────────────────────────────────────────────
COPY requirements.txt .
# Install CPU-only torch first so it doesn't pull the huge CUDA wheel by default
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt

# ── application code ─────────────────────────────────────────────────────────
COPY vision/ vision/
COPY training/ training/
# migrations are applied separately; include for reference
COPY migrations/ migrations/

# ── runtime ──────────────────────────────────────────────────────────────────
# Env vars expected at runtime (pass via -e or --env-file):
#   SUPABASE_URL
#   SUPABASE_SERVICE_KEY
#   FOOTAGE_ROOT   (default: /footage  — mount your fight_footage dir here)

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

ENTRYPOINT ["python", "-m", "vision.batch"]
CMD ["--footage-root", "/footage", "--allow-null-ids", "--device", "cpu", "--interval", "2.0"]
