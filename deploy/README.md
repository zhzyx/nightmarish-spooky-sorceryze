# Tianxuan self-hosted deployment

Single-node Docker Compose stack for the Tianxuan module: a FastAPI service, the
Next.js web shell, and an nginx front door. It is meant for small self-hosted
installations and evaluation, not for high availability.

```
                    host :8080 (TIANXUAN_HTTP_PORT)
                              |
                       +------+------+
                       |    proxy    |  nginx:alpine
                       +------+------+
                         /          \
             /api/*     /            \   everything else
                       v              v
                +-------------+  +-------------+
                |     api     |  |     web     |
                |  uvicorn    |  |  next start |
                |   :8000     |  |   :3000     |
                +------+------+  +-------------+
                       |
                 tianxuan-data
                 /data/tianxuan.db
                 /data/repos/...
                       |
                       +----> external Gitea/Forgejo (optional, not deployed here)
```

Only the `proxy` service publishes a host port. `api` and `web` are reachable
only on the Compose network.

## Files

| Path | Purpose |
| --- | --- |
| `Dockerfile.api` | Python 3.12 image for the FastAPI server; build context is the **repository root** |
| `Dockerfile.api.dockerignore` | Trims the repository-root build context (BuildKit reads it by the `<Dockerfile>.dockerignore` convention) |
| `Dockerfile.web` | Multi-stage Node 22 image for the Next.js app; build context is `apps/tianxuan` |
| `docker-compose.yml` | `api`, `web`, `proxy` services and the `tianxuan-data` volume |
| `nginx.conf` | `/` -> web, `/api/` -> api, WebSocket upgrade for `/api/v1/ws/` |
| `.env.example` | Every supported variable, with comments and no real tokens |

## Build contexts

The API image **must** be built from the repository root. The FastAPI app lives
in `customizations/components/tianxuan/server`, but it imports the sibling
`wenqu` and `duobao` packages through bridge modules. `Dockerfile.api` copies
all three directories into `/app/customizations/components/tianxuan/` and sets:

```
PYTHONPATH=/app/customizations/components/tianxuan/server:/app/customizations/components/tianxuan/wenqu:/app/customizations/components/tianxuan/duobao
```

`WORKDIR` is the `server` directory, so the container command is
`uvicorn main:app`. The image also installs the `git` CLI because the duobao
`GitService` shells out to it for repository/commit operations.

The web image is built from `apps/tianxuan` (`npm ci`, `npm run build`) and
runs `npm run start` (Next.js on port 3000). `NEXT_PUBLIC_*` values are baked
into the browser bundle, so they are Docker build args, not runtime variables.

## Prerequisites

- Docker Engine with the Compose v2 plugin (`docker compose`).
- Roughly 2 GB of free RAM while building the web image; ~1 GB at runtime.
- Optional: an external Gitea/Forgejo instance for repository features.
- No separate Python, Node, or git installation on the host; everything runs in
  containers.

## Quick start

Run from this `deploy/` directory:

```sh
cp .env.example .env
# edit .env: host port, actors, optional Gitea settings
docker compose --env-file .env config     # optional: validate interpolation
docker compose --env-file .env up -d --build
docker compose --env-file .env ps
```

Open <http://localhost:8080/>. Smoke test:

```sh
curl -fsS http://127.0.0.1:8080/api/v1/health
# {"status":"ok"}
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/
# 200
```

From the repository root the equivalent is:

```sh
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

### Create the first user (for actor-based features)

Registration is open on the API; the response contains the `user_id`:

```sh
curl -fsS -X POST http://127.0.0.1:8080/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"tenant_name":"demo","email":"admin@example.com","password":"replace-this-password","name":"Admin"}'
# {"tenant_id":"ten_...","space_id":"spc_...","user_id":"usr_..."}
```

Put the returned `usr_...` id into `.env`:

- `TIANXUAN_ACTOR` - read at request time by the web server for the live panels.
- `NEXT_PUBLIC_TIANXUAN_ACTOR` - baked into the browser bundle; rebuild `web`
  after changing it:

```sh
docker compose --env-file .env up -d --build web
```

With both actors empty the UI still renders, but uses its local demo data
instead of the API. The browser-side editor/status use the same-origin proxy
normally; the server-rendered live panels on `/docs` and `/repos` additionally
need an absolute API base reachable from inside the web container, because
Next.js server components cannot fetch relative URLs. With the recommended
empty base those panels simply fall back to demo data.

## Configuration

All values come from the environment / `deploy/.env`; `docker-compose.yml`
contains no credentials. See `.env.example` for the commented version.

| Variable | Default | Used by | Meaning |
| --- | --- | --- | --- |
| `TIANXUAN_HTTP_PORT` | `8080` | proxy | Host port mapped to nginx port 80 |
| `TIANXUAN_DB` | `/data/tianxuan.db` | api | SQLite file path inside the container |
| `TIANXUAN_REPO_ROOT` | `/data/repos` | api | Directory with bare Git repositories used by requirement commits |
| `TIANXUAN_GITEA_URL` | empty | api | External Gitea/Forgejo base URL; empty disables the integration |
| `TIANXUAN_GITEA_TOKEN` | empty | api | Gitea token (keep in `.env`, never commit) |
| `TIANXUAN_GITEA_OWNER` | empty | api | Optional default repository owner |
| `NEXT_PUBLIC_TIANXUAN_API_BASE` | empty | web build | API origin baked into the browser bundle; empty = same origin |
| `NEXT_PUBLIC_TIANXUAN_ACTOR` | empty | web build | Browser-side actor id for document editing |
| `TIANXUAN_ACTOR` | empty | web runtime | Server-side actor id for the live panels (requires an absolute API base reachable from the web container) |

`NEXT_PUBLIC_TIANXUAN_API_BASE` is intentionally empty by default: the browser
calls `/api/v1/...` on the same origin and nginx forwards `/api/` to the API.
FastAPI has no CORS middleware in this module, so pointing the web app at a
different origin will be rejected by the browser. Keep the same-origin setup
unless you add CORS or a same-origin proxy elsewhere.

## Volumes and persistence

The stack creates one named volume, `tianxuan-data`, mounted at `/data` in the
`api` container:

- `/data/tianxuan.db` - SQLite database (created on first start).
- `/data/repos/` - bare Git repositories referenced by `TIANXUAN_REPO_ROOT`.

The API runs as uid/gid `10001`. A fresh named volume inherits that ownership
from the image. If you replace the named volume with a host bind mount, prepare
it first:

```sh
sudo chown -R 10001:10001 /srv/tianxuan-data
```

### Backup and restore

Stop the API first so the SQLite file is consistent (the deployment does not
enable WAL mode):

```sh
docker compose --env-file .env stop api
docker run --rm -v tianxuan-data:/data -v "$PWD":/backup alpine:3 \
  tar -czf /backup/tianxuan-data-$(date +%Y%m%d-%H%M%S).tgz -C /data .
docker compose --env-file .env start api
```

Restore into the (stopped) API:

```sh
docker compose --env-file .env stop api
docker run --rm -v tianxuan-data:/data -v "$PWD":/backup alpine:3 \
  sh -c 'rm -rf /data/* && tar -xzf /backup/<backup-file>.tgz -C /data && chown -R 10001:10001 /data'
docker compose --env-file .env start api
```

On Windows, run the `docker run` backup/restore commands from WSL or Git Bash
(the `$PWD`/`date` syntax above is POSIX shell).

### Migrating an existing SQLite database

The storage layer applies its idempotent schema bootstrap (`CREATE TABLE IF NOT
EXISTS` plus additive `ALTER TABLE`) when the API starts; there is no separate
migration command. To move an existing local `tianxuan.db` into the volume:

```sh
docker compose --env-file .env up -d --build     # creates the volume
docker compose --env-file .env stop api
docker run --rm -v tianxuan-data:/data \
  -v "<directory-containing-tianxuan.db>":/src:ro alpine:3 \
  sh -c 'cp /src/tianxuan.db /data/tianxuan.db && chown 10001:10001 /data/tianxuan.db'
docker compose --env-file .env start api
```

Do the same, as a directory copy, for any repositories that should be visible
under `/data/repos`. Always take a backup before upgrading to a newer image.

## Operations

```sh
docker compose --env-file .env logs -f api web proxy
docker compose --env-file .env restart api
docker compose --env-file .env down            # keeps the tianxuan-data volume
docker compose --env-file .env down -v         # DESTROYS the database and repositories
```

To update, pull the new source and rebuild:

```sh
git pull
docker compose --env-file .env up -d --build
```

Re-run `up -d --build` after changing any `NEXT_PUBLIC_*` value (they are baked
into the web bundle), and after code changes to either image.

## TLS and the outer proxy

This stack terminates **plain HTTP** only. Do not expose port 8080 to the
internet as-is. Put TLS at an outer reverse proxy or load balancer, keep 8080
on localhost/private network, and forward both normal requests and WebSocket
upgrades to it. Minimal outer nginx shape:

```nginx
server {
    listen 443 ssl http2;
    server_name tianxuan.example.com;

    ssl_certificate     /etc/letsencrypt/live/tianxuan.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tianxuan.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        # Required for /api/v1/ws/:
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
    }
}
```

`$connection_upgrade` is the usual `map $http_upgrade $connection_upgrade`
snippet from the nginx docs. The bundled inner proxy re-resolves `api`/`web`
through Docker's DNS (`127.0.0.11`), so it is Compose-specific.

## Gitea

Gitea/Forgejo is **not** part of this stack. Point `TIANXUAN_GITEA_URL` at an
existing instance and provide a token with repository read/write scope in
`TIANXUAN_GITEA_TOKEN`. The `api` container must be able to reach that URL over
the network. Keep the token in `.env` (git-ignored) or an external secret
manager; it is never written into `docker-compose.yml`.

Without these variables the Gitea-backed repository views report
`configured: false` and the rest of the API keeps working.

## Security and production notes

- The API uses application-level Bearer sessions / `X-Actor`; there is no SSO,
  rate limiting, or TLS here.
- `.env` contains plaintext credentials. Restrict its permissions and do not
  commit it (`deploy/.env` is git-ignored; only `.env.example` is tracked).
- Image tags (`python:3.12-slim`, `node:22-alpine`, `nginx:alpine`) float. Pin
  digests for reproducible production builds.
- No resource limits, log rotation, or restart policy tuning are configured
  beyond `restart: unless-stopped`. Configure Docker's log driver/rotation for
  long-running installs.
- No backups are scheduled automatically; use the backup commands above.

## Known limitations

- **One API process only.** SQLite is single-writer, and the FastAPI WebSocket
  document rooms are in-process memory. Do not scale `api` beyond one replica:
  a second replica would split WebSocket fan-out and contend for the same
  SQLite file. A future PostgreSQL adapter is the intended path for horizontal
  scaling; it is not part of this deployment.
- **Schema bootstrap is startup-time.** There is no standalone migration
  tooling. Back up before image upgrades and expect the storage layer to apply
  additive schema changes on boot.
- **Same-origin web/API.** Without CORS in the API, the web app cannot call a
  cross-origin API from the browser. The bundled proxy provides the supported
  same-origin setup.
- **Server-rendered live panels need an absolute base.** Next.js server
  components cannot fetch relative URLs, so with the recommended empty
  `NEXT_PUBLIC_TIANXUAN_API_BASE` the `/docs` and `/repos` live panels cannot
  reach the API from inside the web container and fall back to demo data. The
  browser editor/status are unaffected. Enabling those panels requires an
  absolute API base reachable from both the browser and the web container,
  plus a matching CORS/same-origin setup.
- **Build-time public env.** `NEXT_PUBLIC_TIANXUAN_API_BASE` and
  `NEXT_PUBLIC_TIANXUAN_ACTOR` require an image rebuild to change.
- **TLS is external.** This stack does not manage certificates or HTTPS.
- **Gitea and Git data are external inputs.** The image does not clone or
  provision repositories; `TIANXUAN_REPO_ROOT` must already contain what the
  UI should use.
- **Compose DNS.** `nginx.conf` assumes Docker's embedded DNS; it is not a
  drop-in config for a non-Compose host.

## Troubleshooting

- `dependency failed to start: container ... api ... is unhealthy` - check
  `docker compose --env-file .env logs api`. The most common causes are a
  missing dependency during `pip install` and a `/data` permission problem.
- `502 Bad Gateway` from nginx - `api` or `web` is not ready; check
  `docker compose --env-file .env ps` and the service logs.
- API returns `400 X-Actor header or Bearer token is required` - the request
  needs an authenticated actor; register a user and pass its id/bearer token.
- API returns `400 TIANXUAN_REPO_ROOT is not configured` or a commit error -
  set `TIANXUAN_REPO_ROOT` (default `/data/repos`) and make sure the target
  repository exists there.
