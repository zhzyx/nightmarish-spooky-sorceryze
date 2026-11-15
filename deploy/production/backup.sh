#!/usr/bin/env bash
# Consistent backup of the Tianxuan data volume, keeping the last 7 archives.
# Usage:
#   bash deploy/production/backup.sh
#   TIANXUAN_BACKUP_DIR=/srv/backups bash deploy/production/backup.sh
set -euo pipefail

DEPLOY_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$DEPLOY_DIR"
BACKUP_DIR=${TIANXUAN_BACKUP_DIR:-$DEPLOY_DIR/backups}
mkdir -p "$BACKUP_DIR"

TS=$(date +%Y%m%d-%H%M%S)
NAME="tianxuan-data-$TS.tgz"

restart_api() {
    docker compose --env-file .env start api >/dev/null 2>&1 || true
}
trap restart_api EXIT

docker compose --env-file .env stop api >/dev/null
docker run --rm --user 0 \
    -v tianxuan-data:/data \
    -v "$BACKUP_DIR":/backup \
    --entrypoint tar tianxuan-api:local \
    -czf "/backup/$NAME" -C /data .
restart_api
trap - EXIT

for _ in $(seq 1 40); do
    if curl -kfsS https://127.0.0.1/api/v1/health >/dev/null 2>&1; then break; fi
    sleep 2
done

ls -1t "$BACKUP_DIR"/tianxuan-data-*.tgz | tail -n +8 | xargs -r rm -f
ls -lh "$BACKUP_DIR/$NAME"
