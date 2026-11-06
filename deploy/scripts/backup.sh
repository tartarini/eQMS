#!/usr/bin/env bash
# Back up the database and uploaded files into one timestamped folder, with a manifest of
# SHA-256 checksums and the latest audit-trail hash so a restore can be verified.
#
#   backup.sh                     # uses DATABASE_URL, DJANGO_MEDIA_ROOT, BACKUP_DIR
#   BACKUP_RETENTION_DAYS=30      # older backups are deleted (default 30)
#
# Runs daily from the scheduler container and before every production deployment.
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL must be set}"
MEDIA_ROOT="${DJANGO_MEDIA_ROOT:-/data/media}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
LABEL="${1:-scheduled}"

case "$DATABASE_URL" in
  postgres*) ;;
  *) echo "backup: only PostgreSQL is supported (DATABASE_URL=${DATABASE_URL%%:*}...)" >&2; exit 1 ;;
esac

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
target="${BACKUP_DIR}/${stamp}-${LABEL}"
partial="${target}.partial"
mkdir -p "$partial"
trap 'rm -rf "$partial"' ERR

echo "backup: database -> ${target}/database.dump"
pg_dump --format=custom --no-owner --no-privileges --file="${partial}/database.dump" "$DATABASE_URL"

echo "backup: files -> ${target}/media.tar.gz"
tar -C "$MEDIA_ROOT" -czf "${partial}/media.tar.gz" .

audit_hash="$(psql "$DATABASE_URL" -At -c \
  "SELECT coalesce((SELECT hash FROM qms_auditevent ORDER BY id DESC LIMIT 1), 'none')")"
audit_count="$(psql "$DATABASE_URL" -At -c "SELECT count(*) FROM qms_auditevent")"

db_sha="$(sha256sum "${partial}/database.dump" | cut -d' ' -f1)"
media_sha="$(sha256sum "${partial}/media.tar.gz" | cut -d' ' -f1)"
cat > "${partial}/manifest.json" <<JSON
{
  "created_utc": "${stamp}",
  "label": "${LABEL}",
  "qms_version": "${QMS_VERSION:-unknown}",
  "audit_events": ${audit_count},
  "latest_audit_hash": "${audit_hash}",
  "files": {
    "database.dump": "${db_sha}",
    "media.tar.gz": "${media_sha}"
  }
}
JSON

mv "$partial" "$target"
trap - ERR
echo "backup: done (${audit_count} audit events, latest hash ${audit_hash:0:16}...)"

if [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]] && (( RETENTION_DAYS > 0 )); then
  find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -name '20*' -mtime +"$RETENTION_DAYS" \
    -print -exec rm -rf {} + | sed 's/^/backup: pruned /'
fi
