#!/usr/bin/env bash
# Restore a backup made by backup.sh, then prove it is intact (validation step IQ-08).
#
#   restore.sh /backups/20261105T023000Z-scheduled
#
# Restores into DATABASE_URL and DJANGO_MEDIA_ROOT, which must be EMPTY: point them at a
# separate restore-test instance, never at production unless you are recovering from loss.
# Checks: file checksums match the manifest, the audit chain verifies, and the latest audit
# hash equals the one recorded at backup time.
set -euo pipefail

src="${1:?usage: restore.sh <backup folder>}"
: "${DATABASE_URL:?DATABASE_URL must be set}"
MEDIA_ROOT="${DJANGO_MEDIA_ROOT:-/data/media}"
manifest="${src}/manifest.json"
[[ -f "$manifest" ]] || { echo "restore: no manifest in ${src}" >&2; exit 1; }

# field KEY [KEY...]: read a value from the manifest
field() {
  python3 -c 'import json, sys
d = json.load(open(sys.argv[1]))
for k in sys.argv[2:]:
    d = d[k]
print(d)' "$manifest" "$@"
}

echo "restore: verifying checksums"
for f in database.dump media.tar.gz; do
  expected="$(field files "$f")"
  actual="$(sha256sum "${src}/${f}" | cut -d' ' -f1)"
  [[ "$expected" == "$actual" ]] || { echo "restore: checksum mismatch for $f" >&2; exit 1; }
done

tables="$(psql "$DATABASE_URL" -At -c "SELECT count(*) FROM pg_tables WHERE schemaname='public'")"
if [[ "$tables" != "0" && "${RESTORE_FORCE:-0}" != "1" ]]; then
  echo "restore: target database is not empty (${tables} tables). Refusing; set RESTORE_FORCE=1 only for disaster recovery." >&2
  exit 1
fi
if [[ -n "$(ls -A "$MEDIA_ROOT" 2>/dev/null)" && "${RESTORE_FORCE:-0}" != "1" ]]; then
  echo "restore: media folder ${MEDIA_ROOT} is not empty. Refusing." >&2
  exit 1
fi

echo "restore: database"
pg_restore --no-owner --no-privileges --exit-on-error --dbname="$DATABASE_URL" "${src}/database.dump"
echo "restore: files"
mkdir -p "$MEDIA_ROOT"
tar -C "$MEDIA_ROOT" -xzf "${src}/media.tar.gz"

echo "restore: verifying audit trail"
python manage.py verify_audit
latest="$(psql "$DATABASE_URL" -At -c \
  "SELECT coalesce((SELECT hash FROM qms_auditevent ORDER BY id DESC LIMIT 1), 'none')")"
expected="$(field latest_audit_hash)"
if [[ "$latest" != "$expected" ]]; then
  echo "restore: latest audit hash ${latest} does not match backup ${expected}" >&2
  exit 1
fi
echo "restore: OK — checksums match, audit chain intact, latest hash ${latest:0:16}... matches"
