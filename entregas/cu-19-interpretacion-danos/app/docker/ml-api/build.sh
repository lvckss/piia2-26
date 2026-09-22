#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
APP_ROOT="$(CDPATH= cd -- "${SCRIPT_DIR}/../.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-webapp-ml-api:local}"

exec docker build \
  -f "${APP_ROOT}/docker/ml-api/Dockerfile" \
  -t "${IMAGE_NAME}" \
  "${APP_ROOT}"
