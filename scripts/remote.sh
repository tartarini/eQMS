#!/usr/bin/env bash
# Day-to-day work on a remote SAMD_QMS server (staging or production VM) over SSH.
# Set-up and releases stay in Ansible (make provision / make deploy); this script is for
# looking at a running server and doing the routine jobs by hand.
#
#   scripts/remote.sh [-e ENV] COMMAND [ARGS...]      ENV: staging (default) or production
#
#   status               containers, health, disk, last deployments
#   health               fetch https://DOMAIN/healthz from here (version, commit, status)
#   logs [SERVICE]       follow logs (app, scheduler, caddy, db; default all)
#   ssh                  interactive shell on the server in the app directory
#   manage ARGS...       run a manage.py command in the app container
#   shell                Django shell in the app container
#   createsuperuser      create an administrator account
#   verify-audit         check the audit trail hash chain
#   backup [LABEL]       take a backup now (default label: manual)
#   backups              list backups on the server
#   fetch-backup NAME    copy one backup folder here, to ./backups/ENV/NAME (contains QMS data)
#   deployments          show DEPLOYMENTS.log
#   tunnel               Django admin through SSH at https://localhost:8443/admin/
#   offsite-backup       copy backups off-site now (also runs nightly), then show the log
#
# The server is the first host under [ENV] in deploy/ansible/inventory.ini. Override with
# QMS_REMOTE_HOST, QMS_REMOTE_USER (default qmsdeploy), QMS_REMOTE_PORT (22),
# QMS_REMOTE_DIR (/opt/samd_qms), QMS_REMOTE_DOMAIN (default: the host name).
# On production, commands that can change data ask for confirmation (QMS_YES=1 skips it).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_NAME=staging
die() { printf 'remote.sh: %s\n' "$*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    -e|--env) ENV_NAME="${2:?--env needs a name}"; shift 2 ;;
    --env=*)  ENV_NAME="${1#*=}"; shift ;;
    *) break ;;
  esac
done

usage() { awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' "$0"; }

inventory_host() {
  local inv="$ROOT/deploy/ansible/inventory.ini"
  [[ -f "$inv" ]] || return 0
  awk -v env="[$ENV_NAME]" '
    /^\[/ { in_env = ($1 == env); next }
    in_env && NF && $1 !~ /^[#;]/ { print $1; exit }' "$inv"
}

HOST="${QMS_REMOTE_HOST:-$(inventory_host)}"
USER_="${QMS_REMOTE_USER:-qmsdeploy}"
PORT="${QMS_REMOTE_PORT:-22}"
DIR="${QMS_REMOTE_DIR:-/opt/samd_qms}"
DOMAIN="${QMS_REMOTE_DOMAIN:-$HOST}"
BACKUP_HOST_DIR="${QMS_REMOTE_BACKUPS:-/var/backups/samd_qms}"
COMPOSE="docker compose --project-directory $DIR -f $DIR/compose.prod.yaml"

need_host() {
  [[ -n "$HOST" ]] || die "no host for '$ENV_NAME'. Copy deploy/ansible/inventory.example.ini to \
inventory.ini and set it, or set QMS_REMOTE_HOST."
}

# Run a command on the server. -t gives a terminal (for shells, logs and prompts).
on_server() {
  local tty=()
  if [[ "$1" == "-t" ]]; then tty=(-t); shift; fi
  need_host
  ssh ${tty[@]+"${tty[@]}"} -p "$PORT" "$USER_@$HOST" "$@"
}

confirm_production() {
  [[ "$ENV_NAME" == "production" && "${QMS_YES:-0}" != "1" ]] || return 0
  printf 'PRODUCTION (%s): %s\n' "$HOST" "$1"
  read -r -p "Type the host name to continue: " answer
  [[ "$answer" == "$HOST" ]] || die "cancelled"
}

quote_args() { local out=() a; for a in "$@"; do out+=("$(printf '%q' "$a")"); done; echo "${out[*]}"; }

command="${1:-help}"
shift || true
case "$command" in
  status)
    on_server "set -e
      echo '== containers'; $COMPOSE ps
      echo; echo '== health'; curl -fsS --max-time 10 https://$DOMAIN/healthz || echo 'healthz FAILED'
      echo; echo '== disk'; df -h / $BACKUP_HOST_DIR | sed 1d
      echo; echo '== last deployments'; tail -n 5 $DIR/DEPLOYMENTS.log 2>/dev/null || echo 'none yet'
      echo; echo '== off-site backups'; tail -n 3 $DIR/OFFSITE.log 2>/dev/null || echo 'never run'"
    ;;
  health)
    need_host
    curl -fsS --max-time 10 "https://$DOMAIN/healthz"; echo
    ;;
  logs)
    on_server -t "$COMPOSE logs -f --tail=200 $(quote_args "$@")"
    ;;
  ssh)
    on_server -t "cd $DIR && exec \$SHELL -l"
    ;;
  manage)
    (( $# )) || die "usage: remote.sh manage COMMAND [ARGS...]"
    confirm_production "manage.py $*"
    on_server -t "$COMPOSE exec app python manage.py $(quote_args "$@")"
    ;;
  shell)
    confirm_production "Django shell (full database access, changes are not audited)"
    on_server -t "$COMPOSE exec app python manage.py shell"
    ;;
  createsuperuser)
    confirm_production "create a superuser"
    on_server -t "$COMPOSE exec app python manage.py createsuperuser"
    ;;
  verify-audit)
    on_server "$COMPOSE exec -T app python manage.py verify_audit"
    ;;
  backup)
    label="${1:-manual}"
    [[ "$label" =~ ^[a-z0-9-]+$ ]] || die "label: lower-case letters, digits and - only"
    on_server "$COMPOSE exec -T app /app/deploy/scripts/backup.sh $label"
    ;;
  backups)
    on_server "ls -1t $BACKUP_HOST_DIR | head -n 30; du -sh $BACKUP_HOST_DIR"
    ;;
  fetch-backup)
    name="${1:?usage: remote.sh fetch-backup NAME (see: remote.sh backups)}"
    [[ "$name" =~ ^[0-9TZ]+-[a-z0-9-]+$ ]] || die "not a backup folder name: $name"
    need_host
    dest="$ROOT/backups/$ENV_NAME/$name"
    mkdir -p "$dest"
    chmod 700 "$ROOT/backups" "$ROOT/backups/$ENV_NAME"
    echo "Copying $name to $dest. It holds QMS records: keep it encrypted and delete it when done."
    rsync -a -e "ssh -p $PORT" "$USER_@$HOST:$BACKUP_HOST_DIR/$name/" "$dest/"
    ;;
  deployments)
    on_server "cat $DIR/DEPLOYMENTS.log 2>/dev/null || echo 'none yet'"
    ;;
  tunnel)
    # /admin/ is not served publicly (finding F7). The server's Caddy serves the whole app,
    # admin included, as https://localhost:8443 on its loopback interface only, and sshd
    # allows forwarding to that port only. Local port 8443 must be free.
    need_host
    echo "Admin for $ENV_NAME: https://localhost:8443/admin/  (Ctrl-C closes the tunnel)"
    echo "The certificate is from Caddy's internal CA: accept the browser warning for localhost."
    ssh -N -o ExitOnForwardFailure=yes -p "$PORT" -L 127.0.0.1:8443:127.0.0.1:8443 "$USER_@$HOST"
    ;;
  offsite-backup)
    on_server "$DIR/offsite-backup.sh && tail -n 5 $DIR/OFFSITE.log"
    ;;
  help|-h|--help) usage ;;
  *) usage; exit 2 ;;
esac
