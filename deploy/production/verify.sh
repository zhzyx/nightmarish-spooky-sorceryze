#!/usr/bin/env bash
# Read-only smoke check for the production HTTPS + cookie-gate profile.
# Usage:
#   TIANXUAN_HOST=tianxuan.example.com \
#   TIANXUAN_ACCESS_TOKEN_FILE=/path/to/access-token \
#   bash deploy/production/verify.sh
set -euo pipefail

DEPLOY_DIR=$(cd "$(dirname "$0")/.." && pwd)
HOST=${TIANXUAN_HOST:?set TIANXUAN_HOST}
BASE="https://$HOST"
TOKEN=${TIANXUAN_ACCESS_TOKEN:-}
if [ -z "$TOKEN" ] && [ -n "${TIANXUAN_ACCESS_TOKEN_FILE:-}" ]; then
    TOKEN=$(cat "$TIANXUAN_ACCESS_TOKEN_FILE")
fi
if [ -z "$TOKEN" ]; then
    echo "set TIANXUAN_ACCESS_TOKEN or TIANXUAN_ACCESS_TOKEN_FILE" >&2
    exit 2
fi

COOKIE_JAR=$(mktemp)
HEADERS=$(mktemp)
trap 'rm -f "$COOKIE_JAR" "$HEADERS"' EXIT

echo "== compose ps =="
if command -v docker >/dev/null 2>&1; then
    (cd "$DEPLOY_DIR" && docker compose --env-file .env ps)
fi

echo "== TLS =="
curl -sS -o /dev/null -w 'https_status=%{http_code} ssl_verify=%{ssl_verify_result}\n' "$BASE/"

echo "== access gate =="
curl -sS -D "$HEADERS" -c "$COOKIE_JAR" -o /dev/null "$BASE/gate?key=$TOKEN"
if grep -qi 'set-cookie: tx_access=' "$HEADERS"; then
    echo "gate cookie: ok"
else
    echo "gate cookie: MISSING" >&2
    exit 1
fi

echo "== with cookie =="
for path in / /docs /issues /requirements /settings; do
    code=$(curl -sS -b "$COOKIE_JAR" -o /dev/null -w '%{http_code}' "$BASE$path")
    echo "$path -> $code"
    [ "$code" = "200" ] || exit 1
done
curl -sS -b "$COOKIE_JAR" -o /dev/null -w 'health:%{http_code}\n' "$BASE/api/v1/health"

echo "== certificate =="
if command -v certbot >/dev/null 2>&1; then
    certbot certificates 2>/dev/null | grep -E 'Certificate Name|Domains|Expiry' || true
fi

echo "== disk =="
df -h "$DEPLOY_DIR" | tail -1
