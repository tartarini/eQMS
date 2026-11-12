#!/bin/sh
# Start Apache for SAMD_QMS.
#
# - Administration site: a self-signed certificate, made once and kept in the tls volume.
# - Public site: the Let's Encrypt certificate written by certbot. Until it exists, a temporary
#   self-signed certificate lets Apache start and answer the ACME challenge.
# - Every hour, if a renewed Let's Encrypt certificate has appeared, the site is rebuilt and
#   Apache reloads gracefully (no dropped connections).
set -eu

: "${QMS_DOMAIN:?set QMS_DOMAIN}"
TLS=/usr/local/apache2/tls
LE=/etc/letsencrypt/live/$QMS_DOMAIN
RENDERED=/usr/local/apache2/conf/extra/qms.conf
mkdir -p "$TLS" "$(dirname "$RENDERED")"

if [ ! -s "$TLS/admin.crt" ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 3650 -subj "/CN=localhost" \
    -addext "basicConstraints=critical,CA:FALSE" \
    -keyout "$TLS/admin.key" -out "$TLS/admin.crt" 2>/dev/null
fi

render() {
  if [ -s "$LE/fullchain.pem" ]; then
    cert="$LE/fullchain.pem"; key="$LE/privkey.pem"
  else
    if [ ! -s "$TLS/fallback.crt" ]; then
      openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj "/CN=$QMS_DOMAIN" \
        -addext "basicConstraints=critical,CA:FALSE" \
        -keyout "$TLS/fallback.key" -out "$TLS/fallback.crt" 2>/dev/null
    fi
    cert="$TLS/fallback.crt"; key="$TLS/fallback.key"
  fi
  sed -e "s|@QMS_DOMAIN@|$QMS_DOMAIN|g" -e "s|@PUBLIC_CERT@|$cert|g" -e "s|@PUBLIC_KEY@|$key|g" \
    /etc/apache2-templates/qms.conf.template > "$RENDERED"
}

fingerprint() {
  if [ -s "$LE/fullchain.pem" ]; then sha256sum "$LE/fullchain.pem" | cut -d' ' -f1; else echo none; fi
}

render
httpd -t
loaded=$(fingerprint)

(
  while sleep 3600; do
    now=$(fingerprint)
    if [ "$now" != "$loaded" ] && httpd -t >/dev/null 2>&1; then
      if render && httpd -k graceful; then
        loaded=$now
        echo "Reloaded Apache with the renewed certificate."
      else
        echo "Reloading Apache with the renewed certificate failed; retrying in an hour." >&2
      fi
    fi
  done
) &

exec httpd-foreground
