#!/usr/bin/env bash

set -euo pipefail

DB_SERVICE="${DB_SERVICE:-db}"
DB_USER="${DB_USER:-speedrulingo}"
DB_NAME="${DB_NAME:-speedrulingo}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required but not found in PATH"
  exit 1
fi

echo "Ensuring Docker Compose service '${DB_SERVICE}' is running..."
docker compose up -d "${DB_SERVICE}" >/dev/null

echo "Wiping database '${DB_NAME}' in service '${DB_SERVICE}'..."
docker compose exec -T "${DB_SERVICE}" psql -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1 <<'SQL'
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO speedrulingo;
GRANT ALL ON SCHEMA public TO public;
SQL

echo "Recreating course_build schema from SQLAlchemy metadata..."
(
  cd backend
  PYTHONPATH=src \
  uv run python -c "from db.base import Base; from db.engine import engine; Base.metadata.create_all(bind=engine)"
)

echo "Done. Postgres schema reset complete and course_build schema created."
