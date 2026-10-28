#!/bin/sh
set -eu

HOST="${ML_API_HOST:-0.0.0.0}"
PORT="${ML_API_PORT:-8001}"
MODEL_PATH="${ML_API_MODEL_PATH:-/models/facebook_sam3}"
RELOAD="${ML_API_RELOAD:-false}"

if [ ! -d "${MODEL_PATH}" ]; then
  echo "[ml-api] no existe el directorio del modelo: ${MODEL_PATH}" >&2
  echo "[ml-api] monta la carpeta host de modelos en /models o ajusta ML_API_MODEL_PATH" >&2
fi

set -- uvicorn ml.api.main:app --host "${HOST}" --port "${PORT}"

if [ "${RELOAD}" = "true" ]; then
  set -- "$@" --reload
fi

exec "$@"
