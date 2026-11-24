# Native candidate HTTP host (#1413)

Set `TIANXUAN_STORAGE_MODE=native` and an explicit absolute `TIANXUAN_NATIVE_DB` file path, then use the existing `uvicorn main:app` entry point. Its parent directory must exist. `TIANXUAN_DB` remains the identity database. Native mode creates no GitService, MergeQueue or merge worker and exposes identity, health and candidate routes; the normal Git mode remains the default and retains existing application routes. Revert to `TIANXUAN_STORAGE_MODE=git` to roll back, retaining both databases. This change does not install or switch production services. Document/issue/model capability unification remains a subsequent integration slice.

Existing `TIANXUAN_REQUIRE_KEYS=1`, admitted `TIANXUAN_TENANT_ID`, and HTTPS public-origin restrictions remain unchanged. In isolated non-production mode, register with `/api/v1/auth/register` and acquire a Bearer session via `/api/v1/auth/session`. Native endpoints never trust X-Actor. Actor and tenant come exclusively from the verified production identity or valid session; viewers cannot write.

### Multiple devices for one account (#2190)

Password login creates an independent session for each login. Browser personal-key login and the native editor's personal-key login enroll an independent device session. Other clients can call `POST /api/v1/auth/device-session` with their source credential and retain the returned token in their credential store. Each registration has a server-generated `device_id` and `credential_id`, also returned by `/api/v1/auth/me`. These identify a device registration, not hardware attestation; copying a device token copies its registration. Never send a device header to select an identity. Keep the device token across retries/restarts; a new enrollment has a new request namespace.

Device grants inherit the source session expiry, cannot enroll another device, and stop authorizing when the source is revoked or expired. Current roles and tenant restrictions still apply. `GET /api/v1/auth/devices` lists the account's registrations whose sessions still exist; `DELETE /api/v1/auth/devices/{device_id}` revokes one of the account's devices. Root personal keys retain their administrator-managed revocation endpoint. Logout revokes the current device session and leaves other devices and the shared root key intact.

Authenticated batches and requirement snapshots scope request keys by tenant, account and device. Receipts include the account, device and credential identifiers, original request key, per-module requested/applied base, read set, written object hashes (null for deletion) and resulting immutable revisions. Content remains accessible through the revision/object APIs under the existing ACL. Receipts and changes commit atomically; retry with the same device token and request key to read the original result. Different devices may reuse a request key without colliding, but cannot overwrite conflicting content: unknown reads still reject any changed base and proven read/write overlaps remain conflicts.

For the ordinary-directory CLI and Git dual-submission adapter, enroll separately on each device with `POST /api/v1/auth/device-session` and put its returned token in that device's trusted credential configuration. Never copy a device token between machines: the server identifies the authenticated registration, not physical hardware. Retain the same device token for retries. The repository service preserves account identity for roles and independent review; another device belonging to the author cannot approve that author's candidate.

The whole-repository service at `/api/v1/native/repos/{repo}` also scopes mutation request keys by tenant, account and device, including downstream checks, reviews and merges. Commit receipts and immutable revision records bind the actor, device, credential, request key, branch, expected parent and full content-hash manifest to the resulting revision. Branch compare-and-swap still allows only one competing commit from a shared expected revision.

Migration is additive (`session_devices`, `native_device_receipts`, `native_repo_device_requests`). Historical account-only receipts remain in `native_receipts` and `native_repo_requests`; trusted legacy store callers can still read them. Device scopes deliberately do not inherit historical account-only receipts whose originating device is unknown. Reconcile an in-flight pre-upgrade request through its original receipt before resubmitting from a new device. Rolling back code preserves the new tables and audit evidence, but old code cannot provide device-scoped receipt lookup; drain device writes before rollback and retain the upgraded database for readback.

The following candidate routes start with `/api/v1/native`, require authentication and reject query parameters.

* `POST /batches`: `{ "request_key": "stable-key", "changes": [{ "module": "module-a", "base": null, "reads": null, "edits": { "file.txt": "aGVsbG8=" } }] }`. A null base creates a module; otherwise use its exact revision. Base64 values write content; null values delete. Optional `dependencies` pins module revisions or `@batch`. Unknown fields are rejected.
* `GET /modules/{module}/head`: current revision or null.
* `GET /modules/{module}/revisions/{revision}`: immutable manifest.
* `GET /modules/{module}/revisions/{revision}/objects/{logical-name}`: verified binary content.
* `POST /compositions`: `{ "selected": { "module-a": "<revision>" } }` resolves an atomic pinned candidate.
* `GET /compositions/{id}`: tenant-bound candidate readback, checking the stored payload digest, pinned dependency closure, revision manifests and referenced bytes. Because NativeStore lacks a lookup method, this adapter uses its private read-only connection interface; no store semantics change.

This slice requires `reads: null`. HTTP consumers cannot yet prove read-set completeness; explicit lists (including empty lists) are rejected. Changes to a module since the supplied base therefore conflict even when the edits appear disjoint. Changes to unrelated modules do not invalidate the base. Trusted reading-session integration is required before exposing object-level rebase. Reading a manifest or object never establishes completeness.

Limits: 8 MiB streamed JSON (Content-Length checked before streaming when present), 4 MiB decoded batch content, 1 MiB per object, 128 module changes or selected roots, and 1024 combined edits/dependency entries. Body overflow stops consumption at the first exceeding chunk. Store operations and native identity lookup run in worker threads. NativeStore's existing SQLite busy timeout remains 30 seconds; observed BUSY/LOCKED errors map to 503 and Retry-After: 1. Conflicts are 409, invalid/unavailable/corrupt native content is 422, oversized requests are 413, and other SQLite errors are generic 500. Error details omit local paths. Candidate acceptance is never approval, check success, release, or consumer receipt. This HTTP boundary exposes no such evidence endpoints.

Regression: `python -m pytest customizations/components/tianxuan/server/test_native_api.py`. Production multi-organization admission, trusted producer provenance, read tracking and governance/consumer wiring remain outside this slice.

## Native daily workflow and requirement snapshots (#1419)

Native mode mounts the existing document, requirement, issue, comments, history,
sharing, AI-view and progress APIs. `/api/v1/capabilities` reports the actual mode
and mounted model/native capabilities; the TianShu status bridge reads it before
requesting Git status. Git repository, import, webhook, merge queue and requirement
commit/git-file routes are absent in native mode. Git-only configuration is not
parsed or required at native startup. Native HTTP and WebSocket routes reject
legacy actor headers/query parameters even when Git compatibility is enabled;
valid sessions and production verified keys remain supported. Production access-key
middleware keeps its strict admission policy.

The mounted model gateway resolves tenant and actor from a valid session or the
production middleware's verified identity. Actor/tenant headers that disagree are
rejected, as are usage queries selecting another tenant. Viewers cannot invoke
models, and production model routes remain administrator-only. Model calls and
usage preserve the existing gateway/budget implementation.

1. `GET /api/v1/native/requirements/{doc_id}/source` returns `source_version`
   (SHA256 of canonical UTF-8 document plus associated issues) and `snapshot`.
   A shared-connection lock and deferred SQLite read transaction make this a
   coherent read even when another connection updates issues concurrently.
2. `POST /api/v1/native/requirements/{doc_id}/snapshots` accepts exactly
   `request_key`, `source_version`, `base`. Use null base only for a new module;
   subsequent operations provide the exact prior native revision. The stable
   operation key is scoped by authenticated tenant/actor. Changing its inputs is
   a conflict. A new operation with a stale source hash or native base is rejected.
3. The response contains the exact `module`, `revision`, source hash and candidate
   `composition`. `snapshot.json` in that revision stores the exact source and
   request binding. It is authoritative; historical retries read its existing
   bytes before consulting current source content, while still checking current
   document write permission. A failed composition call can be retried against
   the already stored revision. Snapshot submission never approves, publishes or
   completes issues. Unknown read dependencies remain conservative (`reads=null`).

The source transaction ends before encoding and native database writes. This is
an exact snapshot of the read instant, not a distributed transaction freezing the
live editor. A later edit cannot change that immutable snapshot; it requires a
new source hash and operation key. The `snapshot-` native receipt namespace is
reserved by this adapter. Source bodies are bounded to 1 MiB. Persistent domain,
native and gateway DB paths must be configured by the host; startup does not
migrate deployment configuration or replace a running service.

Requirement snapshots retain the source document's current read permissions.
The domain database stores the trusted module-to-document binding; native object
JSON cannot grant access. The `requirement-` module namespace is reserved and
generic batches cannot write it. Head, revision, object and composition reads
check the current source ACL; composition creation checks every exact dependency
before writing a composition. Unknown source bindings fail closed, including old
unbound objects. Sharing and revocation apply to historical snapshots as well.
Dependency closure is limited to 128 modules at this HTTP boundary.

The domain binding is committed before native content. A native write failure
may leave an empty reservation, which does not mean a candidate was accepted.
Retry uses the same binding and normal native idempotency. Backups must preserve
both databases; restoring native content without its source binding cannot make
private content public. This is application access control, not protection from
an operator who can directly read either database or a trusted local host API.


## Work order revision links (G12)

In the native workbench, open a Tianxuan issue by number, enter the Duobao module and a full SHA-256 revision or `tag:NAME`, then select **关联多宝提交**. Selecting a linked commit opens the exact revision and its readable issues. **多宝提交 → 打开提交详情** opens the materialized project's current G11 revision, or the exact receipt after a successful submission. Select an issue to open its current I02 detail.

These authenticated routes use the native prefix and the workbench session's `project` query parameter. The module is the native version line returned by G11 in its `branch` field. The association key includes tenant, project, issue ID, module and immutable revision.

| Method and path | Input or result |
| --- | --- |
| `POST /issues/{issue_id}/revisions` | Send `module`, `revision` and optional `tag`. First insertion checks that the tag still points to the submitted revision. A retry of an existing association returns its original receipt. |
| `GET /issues/{issue_id}/revisions` | Read the issue’s pinned revisions and their original tag labels under the current module permissions. |
| `GET /modules/{module}/revisions/{revision}/issue-context` | Read the verified revision’s parent, file count and visible issues in the selected project. |
| `GET /modules/{module}/tags/{tag}` | Resolve the project's current tag to a full revision. |
| `PUT /modules/{module}/tags/{tag}` | Set `revision` with the previously observed `expected` revision, or `null` for creation. A conflicting move returns HTTP 409. |

Viewers can follow visible links. Creating one requires issue write access and source module read access. Tag writes require editor access and a readable module. Moving a project tag or advancing the module head preserves existing links. Each direction checks current access on the issue, including its ancestors, and the module before returning linked records.
