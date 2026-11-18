# Native ordinary requirement entry (#1499)

Paths in this document resolve from the repository root unless explicitly absolute.
This implementation is source-delivered for independent review. No production
installation, live model/provider, listening server or deployment was exercised.

## Unmet primary acceptance

The current product lock spans the entire consume_product call, including model
planning, production, checks, review and publication. Two entries for the same
requirement therefore cannot overlap production, even for disjoint output changes.
Only tasks within one entry can currently run in parallel through Sinan. A second
entry must have the exact same module aliases as the first plan; different scopes
are rejected. Dependency mappings are local to an entry, and next_issues enumerates
that actor's entries. Root has requested a frozen source review before changing
this orchestration. The original multi-user same-product parallel-production goal
is NOT complete. Sequential shared-product ASGI success does not satisfy it.

## Operator installation and ordinary use

Normal `server/main.py` in native mode accepts the operator environment:

* `TIANXUAN_DB`: existing domain database.
* `TIANXUAN_NATIVE_DB`: absolute native content database path.
* `TIANXUAN_NATIVE_INSTALLATION`: absolute immutable installation manifest.
* `TIANXUAN_NATIVE_INSTALLATION_SHA256`: SHA-256 of those manifest bytes.
* `TIANXUAN_NATIVE_STATE`: absolute owned worker/check/registry state directory.

The version 2 manifest has exactly `version`, `mode`, `identity`, `files`,
`commands`, `principals`, `scopes`, `complexity`, and `catalog`. Mode is explicitly
`production` or `deterministic-test`; the capabilities endpoint returns that mode.
`files` maps absolute executable/configuration/source paths to SHA-256. Production
requires every native server/workflow/duobao source and the owned-process helper
in this map. `commands` contains planner, producer, checker, reviewer and dispatcher,
each with fixed `argv` and credential-free `env`. The dispatcher uses the existing
Node `native_entry_driver.mjs`/`driveNative`/Sinan implementation. Operator-installed
checker code must inspect the materialized product in `DUOBAO_INPUT` and must fail
on unacceptable content. Executables run as trusted local programs, not an OS sandbox.

Production planner/reviewer commands invoke `native_entry_runtime.py --config
<absolute broker config> --sha256 <config digest>`; the producer invokes
`native_entry_producer.py` with the same fixed configuration arguments and
`--registry <TIANXUAN_NATIVE_STATE/registry>`. The broker configuration schema is
closed in `load_config`: pinned template, framework manifest, runtime and Node/
Python executables, absolute private state and signer key file, and operator
mandate. Signing keys are read only by the broker process. The planner must be
admitted Yanshi; the reviewer template must declare the reviewer role, a distinct
admitted agent identity and distinct runtime state from the producer. Existing
host-http admission, profile evaluation, budgets and signed runtime remain
mandatory. Different principal strings alone never constitute content approval.
No new model client, task database or scheduler is introduced.

The ordinary caller authenticates through existing session or strict access-key
routes, creates a requirement at `POST /api/v1/requirements`, then sends only
`{requirement, call_id, scopes}` to `POST /api/v1/native/entry/execute`. The caller
never supplies executable paths, factory names, grants, principals or a hand-built
plan. `GET /api/v1/native/entry/capabilities` lists finite installed scopes;
`GET /api/v1/native/entry/{entry}` returns authorized state/progress. Existing
sharing/member APIs permit same-organization collaboration. Strict deployments
continue to require administrator-created personal keys and deny self-registration.

The concrete `OrdinaryEntry` factory constructs NativeWorker, NativeCheckRunner,
NativeRelease, NativeWorkflow, NativeIntegration and its ContinuousIntegration.
Plans are bounded validated DAG proposals. Existing plan_tickets stores parent and
children; each task is authorized against current source and original credential.
Logical finite output modules are namespaced by tenant/requirement. Same-requirement
contributions share an installed lane and base; a later scope expansion requires a
separate requirement. Actual Sinan chooses among the admitted capability catalog;
unknown capabilities cannot run. The original plan, mappings, seed revisions and
receipts remain durable. Parent completion requires all recorded child Issues done.

## Recovery, cancellation and identity

Entry intent and credential digest are persisted in the domain transaction before
notification. Credential plaintext is never persisted. Planner side effects follow
a committed held intent; an unknown planning outcome is not retried. A saved plan
is reused without replanning. Startup reads unfinished entries and native physical
terminals/outbox through the existing workflow. The OS coordinator lock is adjacent
to the native database, so using a different state directory cannot obtain a second
coordinator for the same database. New independent entries can proceed while another
entry waits; same-product entry processing is serialized without holding SQLite locks
across external work. These are event wakeups, not periodic scans.

Each effect and completed wait rechecks original session/key expiry or revocation,
current requirement write authority, source revision and installation bytes. Worker
and checker owned-process cancellation checks run during waits. Independent review
checks every original contributor's current entry authority during its runtime wait,
plus NativeIntegration's original source/module checks before and after review.
Revoked actors do not receive private results. Only the existing physical-settlement
port releases revoked occupancy, and only after exact stored process closure proof.
An unknown external process remains occupied; no PID timeout or automatic relaunch
substitutes for that proof.

IndependentReview reads the exact candidate and original contracts. It requires a
semantic decision, original criteria, exact per-object hashes, reviewer identity and
rationale. It durably records intent before invoking the independent role. Rejected,
missing, mismatched or oversized results never approve. A completed host receipt can
be reused; production recovery calls the broker with `--recover`, which verifies the
original signed binding and reads only the stored completed runtime result. Running/
unknown records never invoke the provider again. Native integration/workflow review
intents remain present while unresolved. Publication recovery continues to use the
existing historical release request, not another publish attempt.

## Limits and validation

This is a bounded v1 implementation. It passes complete source/candidate snapshots;
it is not whole-chain token optimization or arbitrary-project production capability.
Planning and review requests are limited to 100000 serialized UTF-8 bytes; oversized
review snapshots explicitly remain unreviewed and are never truncated. Native model
proposal context may impose a smaller effective bound. Finite installed outputs and
existing DAG/continuous merge constraints still apply. A real conflicting contribution
is retained by existing integration; no unadmitted automatic resolver is installed.
The trusted constructor reserves `context_factory` for #1501, but v1 does not invoke
it and reports `context_tools: false`. No changes were made to #951 or #1343 owners.

`test_native_entry_normal.py` imports actual normal main and uses ASGI HTTP without a
listener: two private tenants, a shared same-tenant requirement and second contributor,
physical producers, content checks, separate semantic checker program, continuous
publication and progress, waiting-session revocation, process closure, restart without
replay, and administrator-provisioned strict-key delivery after revocation. Its role
programs are explicitly deterministic test installations, not real AI models.
`test_native_entry.py` covers atomic intent/plan recovery, unknown/no-replay, concurrent
arrivals, immutable installation withdrawal, process ownership/stream closure, every-
original review authority, oversized-review refusal and read-only signed broker
recovery. The broker protocol test stubs definition admission and external execution;
it does not claim production role or model acceptance.

Run with the existing environment and explicit Node path:

```powershell
$env:NATIVE_TEST_NODE='C:/Users/ROG/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
& D:/GongGong-work/tx-venv/Scripts/python.exe -B -X utf8 customizations/components/tianxuan/server/test_native_entry.py
& D:/GongGong-work/tx-venv/Scripts/python.exe -B -X utf8 customizations/components/tianxuan/server/test_native_entry_normal.py
```

Disable by removing the installation environment and restarting normal main; existing
native/manual storage remains available. Source or configuration digest drift fails
closed. Retain the exact previous installation and all unknown-runtime state when
rolling back; never replay unknown work into a new installation. Actual immutable
package update/rollback, independently reviewed production role configuration, live
models and listening-server/user acceptance remain root delivery steps. Source tests
and mechanism tests do not substitute for those acceptance receipts.

The normal main factory currently runs local-only installed commands on the server host. It does not mount the previously accepted remote-node mechanism. Capabilities expose execution_nodes=local-only. A trusted Python constructor may supply installed_worker as an existing NativeWorker/RemoteNativeWorker sharing the exact native store; this is an adapter injection seam, not validated remote normal-entry acceptance or an HTTP option. Remote node integration and actual local-device/server pairing remain root follow-up acceptance.

Production mode additionally requires the existing strict tenant/key deployment. An entry originally authorized by an ordinary session cannot be promoted into production execution. Known held planning results may recover only through the signed read-only broker; unknown calls never rerun. When a central budget is installed, broker config state must equal its state_dir and execution uses the existing tasks/jid subdirectory. The new signing bridge has also run as a real subprocess with a deterministic evaluated proposal program and a synthetic framework in a test-owned copy; this tests transport/signature/budget/Diting contracts, not real role or AI acceptance.

## Shared-product parallel entry repair (#1499)

The installation's finite scope/module catalog is seeded once per tenant/requirement.
Each receipt pins the aliases, original catalog revisions and scope-provenance digest.
A durable catalog reservation retains the initiating entry/actor/source before seed
creation. Its fixed installed producer principal and product request key recover the
exact native seed after a crash before domain receipt persistence, including when a
different authorized member continues.
A later installation cannot silently mutate that catalog or a lane policy; existing
legacy receipts without this catalog require an explicit migration, not inferred admission.
Only seed/task identity persistence holds the product lock. Planner, producer, check,
review and driver waits occur outside it. A task selects its actual output modules
and accepted dependencies. Existing integration detects conflicting writes and isolates
those contributions while unrelated modules continue through the same product lane.

`POST /api/v1/native/entry/execute` additionally accepts optional `dependencies`, a
unique list of at most 32 existing native task IDs from the same shared requirement.
The server verifies current access and binds each immutable contract and source;
references to future tasks are prohibited, so a new entry cannot introduce a cycle.
Callers never supply grants. Status includes exact task IDs/states and the current
lane policy digest. Acceptance and credential/source mutation events wake waiting
entries; no polling scheduler is installed. Slot races resume only after actual
terminal or acceptance events, using existing recorded task states.

Planning binds the exact entry ID. Mutable workflow effects keep each unfinished
original's credential; a colleague's valid session cannot substitute for it.
Accepted historical provenance is read using current legitimate tenant/document
access, so logout of a completed original does not strand new valid entries.
Each entry settles from its own accepted task mapping. The shared requirement parent
and aggregate remain unfinished until all mapped required tasks have completed.

`POST /api/v1/native/entry/handoff` accepts `requirement` and `expected_policy`.
It verifies actual current same-tenant write access, takes the nonblocking publisher
lock, and compares the exact old policy before changing only its coordinator.
The event records old/new policy digests and actors. A committed acceptance with an
unreconciled lane is physically read back before clearing that lane; any active
publication without committed acceptance stays held under its original owner.
An unknown original is never rebound, replayed or reauthorized by a handoff.

Deterministic normal-ASGI evidence and retained failed probes are indexed in
`data-collection/native-production-entry-parallel-repair-1499.json` (repository-relative).
No provider, network listener, new model client or live production acceptance is implied.

## Bounded shared dispatcher and installed-source integrity

The ordinary coordinator now owns one installed Node pipe process for concurrent
logical drivers. Each driver captures its initiating ContextVar and actor-bound
WorkflowService; inbound messages cannot supply an actor or grant. Production,
checking and review remain in the existing workflow and worker adapters. The pipe
does not serialize whole tasks. Limits are 1024 active logical drivers, 4096 pending
RPCs, 8 MiB per packet and 16 MiB aggregate pending input/output bytes. These are
protocol limits, not an RSS bound or evidence of production model throughput.

Logical completion is recorded as native.entry.dispatch_completed. A logical
receipt explicitly reports physical_terminal=false; coordinator shutdown drains
the shared process and records its actual exit. Canceling a caller leaves its
already-admitted logical driver tracked, including queued start writes. Shared
process startup also survives a detached caller without spawning a second process.
Unknown contexts, malformed replies and
pipe loss fail closed; the same coordinator never silently restarts the process.
Underlying durable workflow effects retain their existing reconciliation rules.

Installed-source digests are reusable only under an explicit trusted-host boundary:
local NTFS files retain deny-write/delete handles; Linux retained and newly opened
descriptors must both report a read-only mount. Linux provisioning must exclude
writable aliases and pre-existing mappings. Other mounts/filesystems use bounded
stream hashing on every verification. Current identity, manifest bytes and live
user authority are still checked; mutable returned dictionaries are not reused as
trusted configuration. close() permanently ends admission and releases handles;
managed replacement requires a newly verified instance. Factory construction/start
failure and normal shutdown release owned installation handles. This does not
make path-based subprocess launch atomic with validation or defend against a
privileged mount administrator. Production mount acceptance is still outstanding.

New authorized work on a completed requirement atomically reopens only its aggregate
parent and synchronizes progress; prior accepted tasks remain immutable. Replayed,
rejected and rolled-back submissions do not reopen that aggregate.
