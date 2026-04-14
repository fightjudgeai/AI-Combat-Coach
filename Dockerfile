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
# Install CPU-only torch + torchvision from the pytorch whl index (matching ABI)
# Pinned to 2.6.0 — latest with a published +cpu torchvision wheel
# then install the rest; --extra-index-url lets pip find other packages from PyPI
RUN pip install --no-cache-dir \
        "torch==2.6.0+cpu" \
        "torchvision==0.21.0+cpu" \
        --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# ── pre-download YOLO model so containers start instantly ────────────────────
RUN python - <<'EOF'
from ultralytics import YOLO
YOLO("yolov8n-pose.pt")   # downloads to /root/.config/Ultralytics cache
EOF

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
#
# Azure Blob Storage (required when video sources use azure:// URIs):
#   AZURE_STORAGE_CONNECTION_STRING   (preferred — from Azure portal → Access keys)
#   — or both of —
#   AZURE_STORAGE_ACCOUNT_NAME
#   AZURE_STORAGE_ACCOUNT_KEY

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

ENTRYPOINT ["python", "-m", "vision.batch"]
CMD ["--footage-root", "/footage", "--allow-null-ids", "--device", "cpu", "--interval", "2.0"]
