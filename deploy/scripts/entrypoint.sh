#!/usr/bin/env bash
# Container entrypoint: wait for the database, optionally migrate, then run the command.
#
# QMS_MIGRATE_ON_START=1 (development) applies migrations and seeds roles on every start.
# In production it stays 0: migrations run explicitly during a controlled deployment.
set -euo pipefail

cd /app

if [[ "${DATABASE_URL:-}" == postgres* ]]; then
  echo "entrypoint: waiting for the database..."
  for attempt in $(seq 1 60); do
    if python manage.py shell -c "from django.db import connection; connection.ensure_connection()" \
         >/dev/null 2>&1; then
      echo "entrypoint: database is up"
      break
    fi
    if [[ "$attempt" == 60 ]]; then
      echo "entrypoint: database not reachable after 120 s" >&2
      exit 1
    fi
    sleep 2
  done
fi

if [[ "${QMS_MIGRATE_ON_START:-0}" == "1" ]]; then
  python manage.py migrate --noinput
  python manage.py seed_qms
fi

mkdir -p "${DJANGO_MEDIA_ROOT:-/data/media}" "${BACKUP_DIR:-/backups}" 2>/dev/null || true

exec "$@"
