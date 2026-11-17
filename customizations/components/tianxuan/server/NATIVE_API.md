# Native candidate HTTP host (#1413)

Set `TIANXUAN_STORAGE_MODE=native` and an explicit absolute `TIANXUAN_NATIVE_DB` file path, then use the existing `uvicorn main:app` entry point. Its parent directory must exist. `TIANXUAN_DB` remains the identity database. Native mode creates no GitService, MergeQueue or merge worker and exposes identity, health and candidate routes; the normal Git mode remains the default and retains existing application routes. Revert to `TIANXUAN_STORAGE_MODE=git` to roll back, retaining both databases. This change does not install or switch production services. Document/issue/model capability unification remains a subsequent integration slice.

Existing `TIANXUAN_REQUIRE_KEYS=1`, admitted `TIANXUAN_TENANT_ID`, and HTTPS public-origin restrictions remain unchanged. In isolated non-production mode, register with `/api/v1/auth/register` and acquire a Bearer session via `/api/v1/auth/session`. Native endpoints never trust X-Actor. Actor and tenant come exclusively from the verified production identity or valid session; viewers cannot write.

All paths below start with `/api/v1/native` and require authentication. No query parameters are supported.

* `POST /batches`: `{ "request_key": "stable-key", "changes": [{ "module": "module-a", "base": null, "reads": null, "edits": { "file.txt": "aGVsbG8=" } }] }`. A null base creates a module; otherwise use its exact revision. Base64 values write content; null values delete. Optional `dependencies` pins module revisions or `@batch`. Unknown fields are rejected.
* `GET /modules/{module}/head`: current revision or null.
* `GET /modules/{module}/revisions/{revision}`: immutable manifest.
* `GET /modules/{module}/revisions/{revision}/objects/{logical-name}`: verified binary content.
* `POST /compositions`: `{ "selected": { "module-a": "<revision>" } }` resolves an atomic pinned candidate.
* `GET /compositions/{id}`: tenant-bound candidate readback, checking the stored payload digest, pinned dependency closure, revision manifests and referenced bytes. Because NativeStore lacks a lookup method, this adapter uses its private read-only connection interface; no store semantics change.

This slice requires `reads: null`. HTTP consumers cannot yet prove read-set completeness; explicit lists (including empty lists) are rejected. Changes to a module since the supplied base therefore conflict even when the edits appear disjoint. Changes to unrelated modules do not invalidate the base. Trusted reading-session integration is required before exposing object-level rebase. Reading a manifest or object never establishes completeness.

Limits: 8 MiB streamed JSON (Content-Length checked before streaming when present), 4 MiB decoded batch content, 1 MiB per object, 128 module changes or selected roots, and 1024 combined edits/dependency entries. Body overflow stops consumption at the first exceeding chunk. Store operations and native identity lookup run in worker threads. NativeStore's existing SQLite busy timeout remains 30 seconds; observed BUSY/LOCKED errors map to 503 and Retry-After: 1. Conflicts are 409, invalid/unavailable/corrupt native content is 422, oversized requests are 413, and other SQLite errors are generic 500. Error details omit local paths. Candidate acceptance is never approval, check success, release, or consumer receipt. This HTTP boundary exposes no such evidence endpoints.

Regression: `python -m pytest customizations/components/tianxuan/server/test_native_api.py`. Production multi-organization admission, trusted producer provenance, read tracking and governance/consumer wiring remain outside this slice.
