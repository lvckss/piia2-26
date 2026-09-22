FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PYTHONPATH=/app \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/tmp/matplotlib \
    HF_HOME=/cache/huggingface \
    TRANSFORMERS_CACHE=/cache/huggingface

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY docker/ml-api/requirements.txt /tmp/requirements.txt

RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir --retries 10 --timeout 120 -r /tmp/requirements.txt

COPY ml /app/ml
COPY docker/ml-api/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && mkdir -p /cache/huggingface /tmp/matplotlib /models

EXPOSE 8001

ENTRYPOINT ["/entrypoint.sh"]
