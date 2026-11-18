# Remote native node installation

This is an explicit host-tool installation in the existing Tianxuan host. It uses
NativeStore, NativeWorkspace, NativeCandidates, NativeWorker/owned_process,
NativeWorkflow and the existing Sinan acceptance outbox. No Git checkout, model
credential, producer command line or environment is sent by the server.

All paths below are absolute host paths. Install the sibling `server`, `duobao`,
`sinan-workorders` modules and the admitted `tools/ainative/owned_process.py` plus
its Windows helper dependencies; installing only native_node.py is insufficient.
Keep the exact source package and its dependency manifest with the host approval.

## Trust and authority

An authorized installer supplies server node descriptors. A node cannot enroll
itself, select a tenant, change the producer or authorize a profile. The public
installation fingerprint is computed by NativeWorker.installation on the actual
node and includes the installed executable, fixed local profile, process helper
and worker implementation. `package` is SHA256 of the installed native_node.py.
Re-enrollment must preserve outstanding exact profile/package assignments until
their physical closure; changing a live installation does not authorize takeover.

The node service and its producers share an OS user. Therefore **all installed
producers are trusted with that user's secrets**. Portable-path validation is not
an OS sandbox and does not isolate an adversarial secret reader. Do not send node
tokens, journals or local configuration to a model. A hostile producer requires
a separate OS security boundary before enrollment.

The server binds a token hash to one node. The outer `/native-nodes` ASGI mount
authenticates that token without passing it to ProductionAccess. Every other URL
continues through the real user middleware. Nodes upload only typed physical and
output closure records; their local candidate/intake/approval is never imported.
The server reconstructs the original task and performs its own current-authority
NativeCandidates intake. Cancellation and current content withdrawal cannot turn
a physical closure into content approval.

## Server assembly

The existing trusted installation factory supplies the domain, checker, release,
authorizer, principals, review/planning/target ports and catalog. Replace its local
worker with this explicit adapter (retain all installed check/review/release ports):

```python
worker = RemoteNativeWorker(native_store, absolute_server_state_dir,
    config['profiles'], authorize=installed_native_authorizer,
    nodes=config['nodes'], single_coordinator=True)
workflow = NativeWorkflow(domain, worker, installed_runner, installed_release,
    installed_workflow_authorizer, capacity=2, catalog=installed_catalog,
    principals=installed_principals, review_candidate=installed_reviewer,
    installed_plan=installed_plan, next_issues=installed_next_issues,
    installed_target=installed_target)
return workflow
```

Trusted server JSON shape (placeholders are not usable secrets):

```json
{"profiles":{"producer-v1":{"timeout":300,"installation":"NODE_COMPUTED_SHA256"}},
 "nodes":{"windows-1":{"tenant":"ENROLLED_TENANT","token_sha256":"SHA256_OF_RANDOM_NODE_TOKEN",
 "profiles":{"producer-v1":"NODE_COMPUTED_SHA256"},"capacity":2,"enabled":true,
 "package":"SHA256_OF_INSTALLED_NATIVE_NODE_PY"}}}
```

```powershell
$env:TIANXUAN_REQUIRE_KEYS = '1'
$env:TIANXUAN_TENANT_ID = 'ENROLLED_TENANT'
$env:TIANXUAN_PUBLIC_ORIGIN = 'https://installed-host.example'
python ABSOLUTE/server/native_remote_host.py --factory installed_host:create_workflow --config ABSOLUTE/server.json --host 127.0.0.1 --port 8769
```

The factory is installed Python code, never a request payload. The host entry
preserves ProductionAccess and installs the narrow router explicitly. Only one
coordinator may own a domain DB: an OS file lock enforces it, and shutdown releases
it. Do not run multiple uvicorn workers or multiple hosts against the SQLite files.

For an existing assembled app use `worker.bind(workflow)` followed by
`mount_native_nodes(create_app(...), worker)`. The outer lifespan forwards the
user application's lifespan and releases the coordinator lock.

## Node assembly

Node-only JSON (installer controlled):

```json
{"server":"https://installed-host.example","database":"D:/NativeNode/node.sqlite",
 "root":"D:/NativeNode/executions","token_file":"D:/NativeNode/private-token.txt",
 "process_helper":"D:/InstalledPackage/tools/ainative/owned_process.py","capacity":2,
 "profiles":{"producer-v1":{"argv":["D:/InstalledTools/producer.exe"],
 "env":{"SYSTEMROOT":"C:/Windows"},"timeout":300,"log_bytes":65536}}}
```

```powershell
python ABSOLUTE/sinan-workorders/native_node.py --config D:/NativeNode/node.json
```

HTTPS certificate verification is required off loopback. A trusted SSH tunnel can
terminate the server connection at `http://127.0.0.1:PORT`; the node opens no port.
`--once` consumes one event batch and waits for workers; it is only a validation
mode and cannot receive cancellation while waiting for a running batch.

The node uses a separate SQLite DB and bounded hash-verified content cache.
Intent is committed before launch; a durable received record precedes cursor
advance. Restart retransmits closed spools and never launches an existing intent.
Unknown intent retains the server slot; an operator must reconcile the original
owner. No PID inference or lease expiry grants a retry. Ordinary transport errors
cause bounded reconnect backoff and spool replay, not model polling or idle scans.
Cancellation before launch writes a trusted no-launch closure. Running cancellation
signals the installed owned_process scope and waits for actual descendant closure.

## Limits, events and recovery

Server global and node capacity are reserved in the same workflow transaction.
An unavailable node leaves the task ready. FIFO skips earlier tasks lacking a
usable node; reservations cannot migrate between nodes. Event cursors are durable;
read/register/read and commit notifications share a condition. Current node and
task permissions are checked after a wait and again before content transfer.

Defaults bound each input/output to 4 MiB, each file to 1 MiB, and each workspace
to 1000 files. Node cache and work directory checks each use a 256 MiB ceiling.
The server permits eight concurrent event waits and two receipt uploads, each
bounded to 9 MiB before JSON decoding. Remote ledger admission stops at 4096
assignments pending installer archival; it never silently deletes ownership.
These are enforced bounds, not evidence of a measured 128/160 MiB deployment.

Physical closure is committed separately from content acceptance. Server failure
between inbox commit and workflow reconciliation is recovered with the immutable
receipt key; an accepted replay cannot overwrite a different original. The node
validates its journal digests before transmission. The server emits its existing
workflow reconciliation event and Sinan continues checking/review/release through
the same installed ports. Receipt transport alone is not product acceptance.

Rollback disables the optional mount/node launcher and retains both databases,
spools, receipt provenance, pending events and unknown ownership. Restore verified
installation bytes before re-enabling. Do not remove active execution directories
or change node identity to bypass an unknown launch.

Validation in test_native_remote.py uses actual authenticated HTTP, separate
Windows node processes/databases, real producers and checker processes, independent
release identities, acceptance-event continuation, real descendant cancellation,
and a coordinator restarted as a separate OS process. It is same-machine evidence.
Cross-machine deployment, measured server memory, 250 tasks and live-model quality
remain separate acceptance work owned by the parent task.

Revoked offers advance the event cursor as `withdraw`, carrying only event and
execution identifiers. Revoked/cancelled manifests disclose no task or sources.
A node with no durable launch intent can acknowledge no-launch physical closure;
an existing unknown intent remains owned until its actual closure is available.
Startup recovery schedules received work through the same bounded executor and
active cancellation registry while the event stream continues. A matching physical
receipt can settle occupied global capacity after actor access is revoked via the
installed worker-only hook; this path returns only state and grants no content,
candidate intake, publication or restored actor permission.
