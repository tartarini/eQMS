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
#   scripts/local.sh reset             delete the local SQLite database and uploaded files
#
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
  manage migrate --no-input
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
  rm -f db.sqlite3
  rm -rf media
  echo "Deleted. Run: scripts/local.sh setup"
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
  help|-h|--help) usage ;;
  *) usage; exit 2 ;;
esac
