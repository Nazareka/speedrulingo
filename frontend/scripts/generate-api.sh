#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ROOT_DIR="$(cd -- "${FRONTEND_DIR}/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
OPENAPI_FILE="${FRONTEND_DIR}/openapi.json"

cd "${BACKEND_DIR}"
PYTHONPATH=src uv run python - <<'PY'
from main import create_app
import json
from pathlib import Path

app = create_app()
output = Path("../frontend/openapi.json")
output.write_text(json.dumps(app.openapi(), ensure_ascii=False), encoding="utf-8")
PY

cd "${FRONTEND_DIR}"
npx openapi-ts --input "${OPENAPI_FILE}"
