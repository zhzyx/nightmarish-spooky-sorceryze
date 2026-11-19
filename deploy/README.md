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

## Production HTTPS and access gate

The base stack is HTTP-only and does not manage certificates or authentication
prompts. The optional [`production/`](production/README.md) profile adds:

- Let's Encrypt TLS on 443 (and 80 for ACME + redirect);
- a cookie access gate with a one-time `/gate?key=...` link;
- a static `/login.html` instruction page for clients without the cookie;
- an internal-only bypass so Next.js SSR can still read the API.

Copy the examples from `production/` as described there. The profile keeps all
application code unchanged; it only replaces the mounted nginx config and adds
a Compose override.

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
| `TIANXUAN_GATEWAY_DB` | `/data/tianxuan_gateway.db` | api | BYOK model-gateway usage/budget SQLite path |
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

## Backup and restore drill

`production/backup.sh` snapshots the `tianxuan-data` volume while the API is
stopped and keeps the last seven archives. Verify and rehearse a restore before
relying on it:

```sh
# 1. Create a backup archive (stops api briefly, restarts it afterwards)
bash deploy/production/backup.sh

# 2. Check the archive contents
tar -tzf deploy/backups/tianxuan-data-*.tgz | head

# 3. Rehearse a restore into a throwaway volume
docker volume create tianxuan-restore
docker run --rm -v tianxuan-restore:/data -v "$PWD/deploy/backups:/backup" \
  --entrypoint tar tianxuan-api:local -xzf /backup/<archive>.tgz -C /data
docker run --rm -v tianxuan-restore:/data --entrypoint sh tianxuan-api:local \
  -c 'sqlite3 /data/tianxuan.db "PRAGMA integrity_check"'
```

`backup.sh` can be pointed at a non-default setup with
`TIANXUAN_DATA_VOLUME`, `TIANXUAN_API_IMAGE` and `TIANXUAN_HEALTH_URL`
(for example an HTTP health URL when TLS is not enabled). The
`duobao-acceptance` workflow runs a full backup/restore drill against the
Compose volume, extracts the archive into a throwaway volume, verifies the
SQLite integrity check and uploads a JSON receipt. It also starts the API against the restored volume and verifies login plus repository listing.

For local installs without Docker, the module ships an end-to-end drill that
creates a backup, verifies every SHA256, restores it and compares repository
bytes plus the SQLite integrity check:

```sh
PYTHONPATH=customizations/components/tianxuan/duobao \
python customizations/components/tianxuan/duobao/backup_drill.py \
  --repo-root /path/to/repos --database /path/to/tianxuan.db \
  --workdir /tmp/duobao-drill --json-out /tmp/duobao-drill.json
```

Exit code `0` writes a JSON receipt with `archive_sha256`, file counts and the
database integrity result; non-zero means the drill failed and the work
directory is kept for diagnosis.

## CI status write-back

The merge gate reads commit statuses from
`GET /api/v1/repos/{owner}/{name}/statuses/{sha}`. Ready-to-copy workflows that
run tests and POST the result live in:

- [`examples/gitea-actions-status.yml`](examples/gitea-actions-status.yml)
- [`examples/github-actions-status.yml`](examples/github-actions-status.yml)

Copy the matching file into the repository's CI directory and configure the
repository secrets `TIANXUAN_URL` and `TIANXUAN_TOKEN` (a Tianxuan Bearer token
with editor access). Then set `TIANXUAN_REQUIRED_CHECKS=tianxuan-ci` on the
Tianxuan server so the merge queue waits for this status. The workflow reports
`success`/`failure` with context `tianxuan-ci`; adjust the test step to the
project's real command.

## Readiness and monitoring

- `GET /api/v1/health` is a liveness probe and always returns `200 {"status":"ok"}`.
- `GET /api/v1/ready` is a readiness probe. It checks the SQLite connection and,
  when `TIANXUAN_REPO_ROOT` is set, that the repository root exists. Missing or
  unreadable state returns `503 {"status":"degraded",...}` so a proxy/monitor can
  stop routing traffic. The merge worker state is reported when a queue exists,
  but a disabled worker does not mark the service unready.
- `GET /api/v1/metrics` returns Prometheus text metrics (documents, issues,
  import jobs, queued merges, active workers) for an admin Bearer token;
  scrape it with `bearer_token` configured in Prometheus.
- Keep the data volume on a monitored disk and alert on `/api/v1/ready` 503
  responses plus free space; `production/verify.sh` prints disk usage and
  certificate expiry for the HTTPS profile.

## Optional native execution package

The API image includes the existing native domain, Sinan dispatcher, frozen
framework definitions, signed host runtime and process transport helpers. Its
Node executable comes from the Debian Node 22 image, matching the Python image's
glibc environment. The Alpine web image is a separate installation. Model CLIs,
provider credentials, task signing keys and operator manifests are not built into
the API image. Installing the image does not admit or start a model task.

Build from the repository root using `deploy/Dockerfile.api`. Its adjacent
Docker ignore file retains the explicit runtime dependencies and excludes the
engine checkout, data receipts, private environment files and unrelated host
tools. Image construction checks Node and Python imports without opening a
database or starting the server.

`docker-compose.native.yml.example` is an explicit optional overlay. Review its
paths, then provide an existing read-only `/installation` directory containing
the admitted manifest and its exact SHA256. Paths inside that manifest resolve
inside the container: code is under `/app`, installed configuration under
`/installation`, and durable task/database state under `/data`. Do not copy a
Windows manifest with host paths or reuse an old digest for new source bytes.
The existing production HTTPS/key overlay still applies; this package does not
change account or organization admission. Never include an unverified native
overlay in the live Compose invocation.

For admitted remote workers and context RPC, also set `TIANXUAN_NATIVE_RUNTIME`
to the absolute container path of the reviewed runtime sidecar and
`TIANXUAN_NATIVE_RUNTIME_SHA256` to its exact digest. Leave both empty when that
capability is not installed. The sidecar binds the ordinary installation digest,
node profiles and context policy. Context token files remain outside model input
and writable task workspaces. The proxy routes `/native-context/` to the API with
its execution bearer preserved and a 256 KiB request limit; production uses the
HTTPS origin, not browser login redirects. A package missing the matching
runtime implementation must not enable this sidecar.

For an upgrade or rollback:

1. Record the exact old/new image IDs, manifest and source hashes, and ownership
   of in-flight tasks. Stop new admission and reconcile actual physical terminals.
   Unknown executions retain their occupancy and receipts; switching an image
   never authorizes replay.
2. Back up the domain and native databases consistently, including required WAL
   state. Rehearse restore into a separate owned volume. Retain the current
   production image, configuration and recovery data.
3. Validate the candidate in an isolated container with a read-only root,
   bounded temporary storage and an owned writable state directory. Verify
   ordinary entry, actual Node transport, revocation, durable progress and
   replacement/reversion against the same isolated state. Import success alone
   is not production acceptance.
4. Only after the complete installation and migration acceptance, switch the
   service to the exact verified image and configuration. If reverting, use the
   verified compatible old installation after handoff. Preserve current task
   journals; never delete the volume or silently rewind accepted work.

The existing small server must also retain sufficient free memory and disk for
its running service and rollback image. Downloading only the verified Node layer
and deriving an isolated test image from an already-installed API base can test
the runtime closure without pulling duplicate full images. Such a derivative
test must record its base and input hashes separately; it does not replace the
normal Dockerfile build or grant production activation.

## Reuse the tested API image

Successful deploy-build jobs publish an Actions artifact named
`tianxuan-api-<run_id>-<run_attempt>`. It contains the tested immutable API image,
its source-file hashes and a manifest with archive hashes, image ID, actual
checkout/tree, candidate head and run identity. Upload follows the container and
Compose checks; it does not attest that other workflows or main delivery passed.

High-concurrency testing is deferred by the user as of 2026-11-19. Ordinary PR
checks retain functional, authorization, bounded retry and recovery tests, but
exclude the synthetic 250-client burst. That retained test can be requested
explicitly through deploy-build's `workflow_dispatch` input `run_context_burst`;
its default is false. The package manifest's `validation_scope` records whether
this test passed or was not run, and always leaves production multi-user capacity
unaccepted. A successful package build does not clear historical burst failures
or establish the 50-user / 250-in-flight target. Linux is the coordinator/server
platform; future capacity acceptance must represent the actual separate Windows
or external execution nodes, rather than all clients in the coordinator budget.

Before installation, select the exact artifact ID from the reviewed run, verify
all applicable checks and the candidate's delivery to main, then verify every
manifest file's byte count and SHA256. A PR job may test a merge checkout, so
compare the actual source tree and relevant package inputs with the delivered
candidate instead of assuming the checkout SHA equals its head. Expired or
unavailable artifacts are unavailable evidence; a same-named replacement is not
an equivalent package.

Check server disk and memory headroom before transferring or loading the archive.
Load the verified archive into Docker and verify the resulting image ID against
the manifest. Run the exact ID in an isolated, bounded container using owned test
state. Keep the current production image, configuration and data intact while
validating installation, update and rollback. No server-side rebuild or production
switch is implied by downloading or loading this package.

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
