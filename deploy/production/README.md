# Production HTTPS and personal access keys

This profile extends the existing Tianxuan Compose stack. It reuses the current
users, roles, hashed sessions, persistent volume and TLS certificate. A shared
`/gate?key=` URL is no longer accepted (410); every user signs in at `/login`
with an administrator-issued personal key. Do not put keys in URLs or logs.

## Upgrade an existing installation

1. Save the current source revision, image IDs, Compose configuration and a
   consistent data backup. Rehearse restoring into a separate volume. Keep the
   old data and images until acceptance; never run `compose down -v`.
2. Build the reviewed API and Web images from the same approved main revision.
   The existing volume is migrated additively; users/documents/repos remain.
3. Copy `docker-compose.override.yml.example` to `deploy/docker-compose.override.yml`
   and `nginx.gate.conf.example` to `deploy/nginx.gate.conf`. Replace
   `__TIANXUAN_HOST__` with the existing certificate hostname.
4. Set `TIANXUAN_TENANT_ID` to the existing administrator's tenant and
   `TIANXUAN_PUBLIC_ORIGIN=https://<hostname>` in the private `.env`. The overlay
   enforces `TIANXUAN_REQUIRE_KEYS=1` and uses the internal API for SSR.
   Do not change the public DNS/certificate or reinitialize the data volume.
5. Bootstrap one personal key for the existing administrator using the domain
   method below in the new API image. Store its output in a private file; do
   not print it in CI logs or commit it. This is a host-admin operation, not
   an unauthenticated HTTP endpoint.
6. Run `docker compose --env-file .env up -d`. Validate nginx before switching
   traffic, then run the read-only verifier and role/revocation acceptance.

Bootstrap shape (replace `existing-admin-id`; execute with the production DB
and capture stdout directly into a mode-600 private file):

```python
import os
from tianxuan_core import Tianxuan
store = Tianxuan(os.environ["TIANXUAN_DB"])
try:
    user = "existing-admin-id"
    print(store.issue_access_key(user, user, "initial administrator", 90)["key"])
finally:
    store.db.close()
```

A key's raw value is returned once. The database stores only its hash in the
existing sessions table and metadata in access_keys. Expiry, revocation and
role changes apply on subsequent requests. Administrators manage accounts,
roles and keys at `/accounts`; viewers cannot write, editors can change
business data, and only administrators can manage users/keys. Password/session
login and public registration are unavailable in this production profile.

## Repository content

Place a bare repository containing the complete approved main tree under the
existing `TIANXUAN_REPO_ROOT` volume. `/repos` browses tracked files through Git,
not arbitrary host paths. Authorized edits produce independent `web/<user>/...`
branches and can enter the existing merge queue. Editing a branch does not
execute or deploy that code. Upstream publication and production upgrades
still require the existing review/delivery workflow. Keep environment files,
credentials and host data outside tracked source.

## Verify and recover

```sh
TIANXUAN_HOST=<hostname> TIANXUAN_ACCESS_TOKEN_FILE=/private/admin-key \
  bash production/verify.sh
```

The script asserts TLS verification, anonymous rejection, obsolete-gate
rejection, authenticated pages/API, cross-origin write rejection and actual
MD/HTML/DOCX/PDF exports. Separately verify viewer denial, editor writes,
revocation, WebSocket ACL changes and data/key persistence after restart.
`backup.sh` returns failure if the API cannot recover; preserve its archive
and investigate before declaring maintenance successful.

Existing certbot webroot renewal and reload hooks remain valid. Fresh hosts
must obtain their certificate before starting this TLS configuration.
For rollback, restore the matching configuration/image/data snapshot together.
If that snapshot predates personal-key authentication, keep public access in
maintenance mode until the secure service is restored; do not silently reopen
the insecure shared-actor deployment.
