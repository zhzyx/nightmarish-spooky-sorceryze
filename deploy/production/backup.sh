#!/usr/bin/env bash
# Consistent backup of the Tianxuan data volume, keeping the last 7 archives.
# Usage:
#   bash deploy/production/backup.sh
#   TIANXUAN_BACKUP_DIR=/srv/backups bash deploy/production/backup.sh
set -euo pipefail

DEPLOY_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$DEPLOY_DIR"
BACKUP_DIR=${TIANXUAN_BACKUP_DIR:-$DEPLOY_DIR/backups}
DATA_VOLUME=${TIANXUAN_DATA_VOLUME:-tianxuan-data}
API_IMAGE=${TIANXUAN_API_IMAGE:-tianxuan-api:local}
mkdir -p "$BACKUP_DIR"

TS=$(date +%Y%m%d-%H%M%S)
NAME="tianxuan-data-$TS.tgz"

restart_api() {
    docker compose --env-file .env start api
}
trap restart_api EXIT

docker compose --env-file .env stop api >/dev/null
docker run --rm --user 0 \
    -v "$DATA_VOLUME":/data \
    -v "$BACKUP_DIR":/backup \
    --entrypoint tar "$API_IMAGE" \
    -czf "/backup/$NAME" -C /data .
restart_api

healthy=0
for _ in $(seq 1 40); do
    if docker compose --env-file .env exec -T api python -c \
      'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/api/v1/health",timeout=3).read()' >/dev/null 2>&1; then healthy=1; break; fi
    sleep 2
done
[ "$healthy" = 1 ] || { echo "Backup saved, but API recovery failed" >&2; exit 1; }
trap - EXIT

ls -1t "$BACKUP_DIR"/tianxuan-data-*.tgz | tail -n +8 | xargs -r rm -f
ls -lh "$BACKUP_DIR/$NAME"
