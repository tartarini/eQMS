#!/usr/bin/env bash
# Local development WITHOUT Docker: a virtualenv in .venv, SQLite (or your own PostgreSQL),
# emails printed to the console. Works from a plain terminal or PyCharm's terminal.
# For the Docker stack (PostgreSQL + Mailpit, same image as production) use `make dev` instead.
#
#   scripts/local.sh setup [--clean]   create .venv, install, migrate, load demo data
#                                      (--clean: empty QMS with seed_qms, then createsuperuser)
#   scripts/local.sh run [PORT]        start the dev server (default 8000)
#   scripts/local.sh test [LABELS...]  run the tests (default: qms)
#   scripts/local.sh ui [--headed]     run only the browser (Playwright) interface tests
#   scripts/local.sh oq [NAME]         write OQ evidence to ./oq_evidence
#   scripts/local.sh jobs              run the daily jobs once (PMS, reminders, audit check)
#   scripts/local.sh manage ARGS...    any manage.py command, e.g. manage createsuperuser
#   scripts/local.sh check             Django system checks and missing-migrations check
#   scripts/local.sh migrate           apply pending migrations; backs up first only if any are pending
#   scripts/local.sh backup [LABEL]    back up the local database and uploaded files to backups/local/
#   scripts/local.sh restore DIR       restore a backup folder (made here, or copied from the server),
#                                      then migrate its data to this code's version
#   scripts/local.sh reset             delete the local database and uploaded files (backs up first)
#
# After git pull or a branch switch, the git hooks in .githooks run `migrate` for you.
# Settings come from the environment and, if present, ./.env.local (KEY=value lines, not
# committed). Set DATABASE_URL there to use a PostgreSQL server instead of SQLite.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VENV="${QMS_VENV:-$ROOT/.venv}"
PY="$VENV/bin/python"

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
die() { printf 'local.sh: %s\n' "$*" >&2; exit 1; }

load_env() {
  if [[ -f .env.local ]]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env.local
    set +a
  fi
  export DJANGO_DEBUG="${DJANGO_DEBUG:-1}"
  export QMS_BASE_URL="${QMS_BASE_URL:-http://localhost:${PORT:-8000}}"
  QMS_COMMIT="${QMS_COMMIT:-$(git rev-parse HEAD 2>/dev/null || true)}"
  export QMS_COMMIT
}

need_venv() {
  [[ -x "$PY" ]] || die "no virtualenv at $VENV. Run: scripts/local.sh setup"
}

find_python() {
  local candidate
  for candidate in "${QMS_PYTHON:-}" python3.13 python3; do
    [[ -n "$candidate" ]] || continue
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 12))' 2>/dev/null; then
      echo "$candidate"; return
    fi
  done
  die "Python 3.12 or newer is needed (3.13 matches production). Set QMS_PYTHON to its path."
}

manage() { "$PY" manage.py "$@"; }

cmd_setup() {
  local clean=0
  [[ "${1:-}" == "--clean" ]] && clean=1
  if [[ ! -x "$PY" ]]; then
    local base; base="$(find_python)"
    say "Creating virtualenv $VENV with $($base --version)"
    "$base" -m venv "$VENV"
  fi
  say "Installing requirements"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -r requirements.txt -r requirements-dev.txt
  say "Installing Chromium for the interface tests (Playwright)"
  "$PY" -m playwright install chromium
  if [[ ! -f .env.local ]]; then
    say "Writing .env.local (local settings, not committed)"
    cat > .env.local <<'EOF'
# Local settings for scripts/local.sh. Not committed. Never put production secrets here.
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
QMS_SSO_ALLOWED_DOMAINS=
# Use PostgreSQL instead of SQLite (e.g. `docker compose up -d db` gives this one):
# DATABASE_URL=postgres://qms:qms@localhost:5432/qms
# Real email instead of the console (e.g. `docker compose up -d mail`, UI on :8025):
# DJANGO_EMAIL_HOST=localhost
# DJANGO_EMAIL_PORT=1025
# DJANGO_EMAIL_TLS=0
# Single sign-on test apps (callback: http://localhost:8000/accounts/<provider>/login/callback/):
# SSO_GOOGLE_CLIENT_ID=
# SSO_GOOGLE_SECRET=
# SSO_ORCID_CLIENT_ID=
# SSO_ORCID_SECRET=
# SSO_ORCID_DOMAIN=sandbox.orcid.org
EOF
  fi
  load_env
  if git rev-parse --git-dir >/dev/null 2>&1; then
    git config core.hooksPath .githooks
    say "Git hooks on: after a pull or branch switch, pending migrations are applied (after a backup)"
  fi
  say "Migrating the database"
  manage migrate --no-input
  if manage shell -c 'from qms.models import Device; import sys; sys.exit(Device.objects.exists())'; then
    if (( clean )); then
      say "Seeding an empty QMS (roles, numbering)"
      manage seed_qms
      say "Create the first administrator"
      manage createsuperuser
    else
      say "Loading demo data"
      manage load_demo_data
    fi
  else
    say "Database already has devices; leaving its data alone (scripts/local.sh reset to start over)"
  fi
  cat <<EOF

Ready. Start the server with:   scripts/local.sh run
Then open http://localhost:8000/login/
EOF
  (( clean )) || echo "Demo logins: engineer_person, qa_person, qa2_person, cso_person (password demo-pass-123)"
  cat <<EOF

PyCharm: Settings > Project > Python Interpreter > Add > Existing: $VENV/bin/python
Run configuration: Django server, or script manage.py with "runserver", working dir $ROOT,
environment from .env.local (EnvFile plugin) or the same KEY=value pairs pasted in.
EOF
}

cmd_run() {
  need_venv
  PORT="${1:-8000}"
  load_env
  cmd_migrate
  say "Serving on http://localhost:$PORT (emails print here unless DJANGO_EMAIL_HOST is set)"
  exec "$PY" manage.py runserver "127.0.0.1:$PORT"
}

cmd_test() {
  need_venv; load_env
  (( $# )) || set -- qms
  manage test "$@"
}

cmd_ui() {
  need_venv; load_env
  if [[ "${1:-}" == "--headed" ]]; then export QMS_UI_HEADED=1 QMS_UI_SLOWMO="${QMS_UI_SLOWMO:-300}"; fi
  manage test qms.test_ui
}

cmd_oq() {
  need_venv; load_env
  local name="${1:-$(git config user.name 2>/dev/null || whoami)}"
  manage run_oq --executed-by "$name" --release dev --output oq_evidence
  echo "Evidence: $ROOT/oq_evidence/oq_report.html"
}

cmd_jobs() {
  need_venv; load_env
  manage generate_pms_activities
  manage send_reminders
  manage verify_audit
}

cmd_check() {
  need_venv; load_env
  manage check
  manage makemigrations --check --dry-run
  echo "Checks passed. Test tracing to requirements is checked by: scripts/local.sh oq"
}

cmd_reset() {
  load_env
  if [[ -n "${DATABASE_URL:-}" ]]; then
    die "DATABASE_URL is set ($DATABASE_URL). Reset that database yourself; this only removes SQLite."
  fi
  read -r -p "Delete db.sqlite3 and ./media (all local data)? [y/N] " answer
  [[ "$answer" == [yY]* ]] || { echo "Nothing deleted."; return; }
  backup_now pre-reset
  rm -f db.sqlite3
  rm -rf media
  echo "Deleted. Run: scripts/local.sh setup"
}

# --- backups, migrations and restore ----------------------------------------------------
# A local backup goes to backups/local/<stamp>-<label>/ (git-ignored), in the same layout as a
# server backup: the database, media.tar.gz and manifest.json with SHA-256 checksums.
# SQLite is saved as database.sqlite3, PostgreSQL as database.dump (pg_dump, custom format).
# A server backup (deploy/scripts/backup.sh) is a PostgreSQL dump, so it restores here only
# when DATABASE_URL points at PostgreSQL: docker compose up -d db, then set DATABASE_URL.

media_root() { echo "${DJANGO_MEDIA_ROOT:-$ROOT/media}"; }

db_kind() {
  if [[ -z "${DATABASE_URL:-}" ]]; then echo sqlite; return; fi
  case "$DATABASE_URL" in
    postgres*) echo postgres ;;
    *) die "only SQLite and PostgreSQL are supported (DATABASE_URL=${DATABASE_URL%%:*}...)" ;;
  esac
}

# Run a command in the PostgreSQL service of docker compose (the local PostgreSQL).
compose_db() {
  docker compose version >/dev/null 2>&1 || die "PostgreSQL needs Docker here. Start it: docker compose up -d db"
  docker compose exec -T db "$@"
}

# Keep the newest QMS_LOCAL_BACKUPS_KEEP backups (default 20); older ones are deleted.
prune_backups() {
  [[ -d "$ROOT/backups/local" ]] || return 0
  find "$ROOT/backups/local" -mindepth 1 -maxdepth 1 -type d -name '2*' |
    sort -r | tail -n +"$(( ${QMS_LOCAL_BACKUPS_KEEP:-20} + 1 ))" |
    while IFS= read -r old; do
      rm -rf "$old" && echo "backup: removed old backup ${old##*/}"
    done
  return 0
}

# backup_now LABEL: copy the database and uploads into a new backup folder.
backup_now() {
  local label="$1" kind dbfile stamp target partial
  kind="$(db_kind)"
  if [[ "$kind" == sqlite && ! -f "$ROOT/db.sqlite3" ]]; then
    echo "Nothing to back up yet: there is no local database."
    return 0
  fi
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  target="$ROOT/backups/local/${stamp}-${label}"
  partial="${target}.partial"
  mkdir -p "$partial"
  trap 'rm -rf "$partial"' ERR
  say "Backing up local data to backups/local/${stamp}-${label}"
  if [[ "$kind" == postgres ]]; then
    dbfile=database.dump
    compose_db pg_dump -U qms -d qms --format=custom --no-owner --no-privileges > "$partial/$dbfile"
  else
    dbfile=database.sqlite3
    # The sqlite3 backup API copies a consistent snapshot, even while the dev server runs.
    "$PY" -c 'import sqlite3, sys
src, dst = sqlite3.connect(sys.argv[1]), sqlite3.connect(sys.argv[2])
src.backup(dst)
dst.close(); src.close()' "$ROOT/db.sqlite3" "$partial/$dbfile"
  fi
  mkdir -p "$(media_root)"
  tar -C "$(media_root)" -czf "$partial/media.tar.gz" .
  "$PY" "$ROOT/scripts/backup_manifest.py" write "$partial" "$label" "$kind" "$dbfile"
  mv "$partial" "$target"
  trap - ERR
  prune_backups
}

cmd_backup() {
  need_venv; load_env
  local label="${1:-manual}"
  [[ "$label" =~ ^[a-z0-9-]+$ ]] || die "label: lower-case letters, digits and - only"
  backup_now "$label"
}

# Apply pending migrations. Lists them, backs up, then migrates. Does nothing if none are pending.
cmd_migrate() {
  need_venv; load_env
  local plan
  plan="$(manage migrate --plan 2>&1)" || { echo "$plan" >&2; die "cannot read the migration plan (is PostgreSQL running?)"; }
  if grep -q 'No planned migration operations' <<<"$plan"; then
    echo "Local database is up to date with this code."
    return 0
  fi
  say "Migrations to apply to your local data:"
  grep -E '^[a-z_]+\.[0-9]{4}' <<<"$plan" | sed 's/^/  /' || true
  backup_now pre-migrate
  manage migrate --no-input
}

cmd_restore() {
  need_venv; load_env
  local src="${1:-}" kind dbfile media answer
  [[ -n "$src" ]] || die "usage: scripts/local.sh restore <backup folder>   (folders: ls backups/local)"
  [[ -f "$src/manifest.json" ]] || die "no manifest.json in $src"
  src="$(cd "$src" && pwd)"
  kind="$(db_kind)"
  if [[ -f "$src/database.dump" ]]; then dbfile=database.dump
  elif [[ -f "$src/database.sqlite3" ]]; then dbfile=database.sqlite3
  else die "$src has no database.dump or database.sqlite3"
  fi
  if [[ "$dbfile" == database.dump && "$kind" != postgres ]]; then
    die "this backup is PostgreSQL, but the local database is SQLite. Start PostgreSQL (docker compose up -d db), set DATABASE_URL in .env.local, then restore again."
  fi
  if [[ "$dbfile" == database.sqlite3 && "$kind" != sqlite ]]; then
    die "this backup is SQLite, but DATABASE_URL is set. Unset it to restore this backup."
  fi
  "$PY" "$ROOT/scripts/backup_manifest.py" verify "$src"
  media="$(media_root)"
  [[ -n "$media" && "$media" != / ]] || die "refusing to restore into media folder '$media'"

  echo "This replaces the local database and uploaded files with the backup."
  echo "Stop the dev server first. The current local data is backed up before anything changes."
  if [[ "${QMS_YES:-0}" != 1 ]]; then
    read -r -p "Restore $(basename "$src")? [y/N] " answer
    [[ "$answer" == [yY]* ]] || { echo "Nothing changed."; return 0; }
  fi
  backup_now pre-restore

  say "Restoring the database"
  if [[ "$kind" == postgres ]]; then
    compose_db dropdb -U qms --if-exists qms
    compose_db createdb -U qms qms
    docker compose cp "$src/$dbfile" db:/tmp/restore.dump
    compose_db pg_restore -U qms -d qms --no-owner --no-privileges --exit-on-error /tmp/restore.dump
    compose_db rm -f /tmp/restore.dump
  else
    rm -f db.sqlite3 db.sqlite3-wal db.sqlite3-shm
    cp "$src/$dbfile" db.sqlite3
  fi

  say "Restoring uploaded files"
  rm -rf "$media"
  mkdir -p "$media"
  tar -C "$media" -xzf "$src/media.tar.gz"

  say "Migrating the restored data to this code's version"
  cmd_migrate
  say "Checking the audit trail"
  manage verify_audit
  echo "Restored $(basename "$src"). If anything above failed, the data from before the restore is in backups/local/ (pre-restore)."
}

usage() { awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$0"; }

command="${1:-help}"
shift || true
case "$command" in
  setup)  cmd_setup "$@" ;;
  run)    cmd_run "$@" ;;
  test)   cmd_test "$@" ;;
  ui)     cmd_ui "$@" ;;
  oq)     cmd_oq "$@" ;;
  jobs)   cmd_jobs ;;
  manage) need_venv; load_env; manage "$@" ;;
  check)  cmd_check ;;
  reset)  cmd_reset ;;
  migrate) cmd_migrate ;;
  backup) cmd_backup "$@" ;;
  restore) cmd_restore "$@" ;;
  help|-h|--help) usage ;;
  *) usage; exit 2 ;;
esac
