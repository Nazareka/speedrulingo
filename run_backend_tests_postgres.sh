#!/usr/bin/env bash

set -euo pipefail

DB_SERVICE="${DB_SERVICE:-db}"
DB_USER="${DB_USER:-speedrulingo}"
DB_PASSWORD="${DB_PASSWORD:-speedrulingo}"
DB_NAME="${DB_NAME:-speedrulingo}"
TEST_DB_NAME="${TEST_DB_NAME:-speedrulingo_test}"
TEST_DATABASE_URL="${SPEEDRULINGO_TEST_DATABASE_URL:-postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@localhost:5432/${TEST_DB_NAME}}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required but not found in PATH"
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but not found in PATH"
  exit 1
fi

echo "Ensuring Docker Compose service '${DB_SERVICE}' is running..."
if [ -z "$(docker compose ps -q "${DB_SERVICE}")" ]; then
  docker compose up -d "${DB_SERVICE}" >/dev/null
fi

echo "Creating/resetting test database '${TEST_DB_NAME}'..."
docker compose exec -T "${DB_SERVICE}" psql -U "${DB_USER}" -d postgres -v ON_ERROR_STOP=1 >/dev/null <<SQL
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '${TEST_DB_NAME}' AND pid <> pg_backend_pid();

DROP DATABASE IF EXISTS ${TEST_DB_NAME};
CREATE DATABASE ${TEST_DB_NAME} OWNER ${DB_USER};
SQL

echo "Running backend tests against ${TEST_DATABASE_URL}..."
pytest_output_file="$(mktemp)"
trap 'rm -f "${pytest_output_file}"' EXIT

if (
  cd backend
  SPEEDRULINGO_DATABASE_URL="${TEST_DATABASE_URL}" \
  SPEEDRULINGO_TEST_DATABASE_URL="${TEST_DATABASE_URL}" \
  env -u VIRTUAL_ENV uv run pytest
) >"${pytest_output_file}" 2>&1; then
  if grep -q '^=============================== warnings summary ===============================$' "${pytest_output_file}"; then
    awk '
      /^=============================== warnings summary ===============================$/ {in_warnings=1}
      in_warnings && /^==================================== PASSES ====================================$/ {in_warnings=0; next}
      in_warnings {print}
    ' "${pytest_output_file}"
    echo
  fi
  tail -n 1 "${pytest_output_file}"
else
  cat "${pytest_output_file}"
  exit 1
fi
