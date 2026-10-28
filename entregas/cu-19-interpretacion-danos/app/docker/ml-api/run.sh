#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
APP_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "${APP_ROOT}/../.." && pwd)"

IMAGE_NAME="${IMAGE_NAME:-webapp-ml-api:local}"
CONTAINER_NAME="${CONTAINER_NAME:-webapp-ml-api}"
HOST_PORT="${HOST_PORT:-8001}"
MODEL_ROOT="${MODEL_ROOT:-${PROJECT_ROOT}/models}"

if [ ! -d "${MODEL_ROOT}/facebook_sam3" ]; then
  echo "[ml-api] no existe ${MODEL_ROOT}/facebook_sam3" >&2
  echo "[ml-api] ajusta MODEL_ROOT antes de lanzar el contenedor" >&2
fi

exec docker run --rm \
  --name "${CONTAINER_NAME}" \
  -p "${HOST_PORT}:8001" \
  -e ML_API_HOST=0.0.0.0 \
  -e ML_API_PORT=8001 \
  -e ML_API_STRATEGY="${ML_API_STRATEGY:-baseline}" \
  -e ML_API_MODEL_PATH="${ML_API_MODEL_PATH:-/models/facebook_sam3}" \
  -e ML_API_ENABLE_ROI_VERIFICATION="${ML_API_ENABLE_ROI_VERIFICATION:-false}" \
  -e ML_API_INCLUDE_VISUALIZATION="${ML_API_INCLUDE_VISUALIZATION:-false}" \
  -e ML_API_VISUALIZATION_FORMAT="${ML_API_VISUALIZATION_FORMAT:-PNG}" \
  -e ML_API_SCORE_THRESHOLD="${ML_API_SCORE_THRESHOLD:-0.6}" \
  -e ML_API_MASK_THRESHOLD="${ML_API_MASK_THRESHOLD:-0.5}" \
  -e ML_API_PROMPT_BATCH_SIZE="${ML_API_PROMPT_BATCH_SIZE:-6}" \
  -e ML_API_DEVICE="${ML_API_DEVICE:-}" \
  -v "${MODEL_ROOT}:/models:ro" \
  -v ml_api_hf_cache:/cache/huggingface \
  "${IMAGE_NAME}"
