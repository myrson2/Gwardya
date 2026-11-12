#!/usr/bin/env bash
# Apply db/setup.sql with the app password injected from backend/.env.
# Run from WSL:  bash backend/db/setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "error: $ENV_FILE not found — copy .env.example to .env first." >&2
  exit 1
fi

DB_PASSWORD="$(sed -nE 's|^DATABASE_URL=.*rbac_app:([^@]+)@.*$|\1|p' "$ENV_FILE" | head -n1)"
if [[ -z "$DB_PASSWORD" ]]; then
  echo "error: could not read the app password from DATABASE_URL in .env" >&2
  exit 1
fi

SQL="$(sed "s|__RBAC_APP_PASSWORD__|${DB_PASSWORD}|g" "$ROOT/db/setup.sql")"

sudo mysql --protocol=socket -uroot <<< "$SQL"

echo "ok: rbac_learning + rbac_learning_test and the rbac_app user are ready"
