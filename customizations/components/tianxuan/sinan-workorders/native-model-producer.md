# Installed native model producer (host_tool)

`native_model_producer.py` is a trusted fixed NativeWorker executable. It consumes
an immutable host-private registry, a signed existing host-http runtime grant,
`NATIVE_CONTEXT`, and the actual owned `NATIVE_WORKSPACE`. It does not replace
Sinan routing, capability evaluation, NativeWorker, or NativeIntegration.

Install the fixed launcher argv `[python, "-B", "-X", "utf8", absolute_launcher,
"--registry", absolute_private_registry_directory]` in the existing worker.
The registry directory must be outside all model-writable workspaces. Host code
must pin `source_digest()` in its installation verifier; this includes runtime,
launcher, NativeWorker/NativeWorkspace and model host implementation. Worker
installation also hashes existing absolute argv files. A registry is a directory,
not a mutable argv file: unrelated registrations do not invalidate running tasks.
The trusted producer environment may contain the authority signing key for grant
verification. The installed model environment is explicit and rejects that key
by name or value; it is never inherited from the producer process.

After NativeWorkflow.authorize_task yields the original execution digest, prepare
a grant whose `task.input` contains `native_request` and `native_binding` as in
`test_native_model_producer.admit`. Binding includes exact execution, absolute
workspace, source digest, original definition, selected UTF-8 file map, explicit
finite write paths and acceptance. Wildcard write scopes must be expanded by the
host to a finite list. Use `register(registry, execution, grant, framework)` before
workflow.execute. Registration is immutable and refuses rebinding. The actual
launcher reads and verifies the original materialization before any model call.
One production step is supported; binary context and missing parent directories
are rejected. Model outputs cannot select executable, environment or authority.
The signed plan selects agent_id: registered role permission and model capability
are separate requirements. Synthetic yanshi fixtures do not admit a general code
production role; a live host must choose an actually admitted role and mandate.

The optional protocol is `codex-native-proposal`. Profile fields add
`native_installation` (the existing NativeModelHost installation), its
`installation_digest`, `output_token_limit: "unsupported"`, and
`response_bytes: 524288`. `timeout_seconds` must equal installed timeout (<=600).
The plan must set `max_output_tokens: null`, `output_token_limit: "unsupported"`
and a positive bounded max_calls. No Codex output-token configuration is invented.
524288 is the outer process receipt byte limit; proposal JSON remains <=262144,
each file <=131072, and the complete effective request <=131072. Input overflow
fails before process launch without truncation. All actual runtime governance and
step messages are included once in effective context; protocol evidence separately
binds original request and governance to the validated effective input digest.

Use existing evaluate.py with representative native requests and proposal schema,
then its report digest/evidence fields and existing grant signing. The optional
`validation_probe` absolute path and SHA are only for deterministic installed
process tests; runner forbids such profiles unless task.validation_only is true.
Synthetic evaluation never admits production. Installation, runtime or evaluation
changes reject old grants; old live #1480 evidence remains evidence of that old
candidate only.

Every CLI grant requires a signed `central_budget` with absolute state_dir,
max_calls, max_concurrent and authority_ref. Per-task state is exactly
`central/state_dir/tasks/jid_for(task)`. A short SQLite transaction reserves each
task's whole maximum call budget permanently and a temporary concurrency lease.
Task locks are separate. Reauthorization cannot reset task budget or move its
journal. Interrupted active leases require host reconciliation; no automatic lease
reclamation exists. Unknown model outcomes never auto-retry or fall back. Existing
explicit runtime recover remains an operator decision, not proof of remote cancel.

CLI counters remain `protocol_evidence.usage.raw` with thread/turn and last/total
unchanged. HTTP usage is empty for this protocol; existing NativeWorker terminal
usage stays null. Request/turn identity, installation and runtime journal associate
actual calls to execution. A failed proposal can retain independently bound usage.

After validation the launcher applies only allowed paths under captured workspace
ownership. Any partial write failure exits unsuccessfully: NativeWorker records
physical process closure but accepts no candidate. Partial files remain inspection
evidence. A successful proposal is still only input to ordinary candidate intake,
checks, independent review and NativeIntegration acceptance. Disabling the installed
launcher rolls back this optional entry; preserve journals and unresolved executions.
No real provider evaluation, production grant, deployment or equal-task GitService
comparison is established by these tests. Those remain separate delivery evidence.

## Host preparation example

The following runs only trusted host preparation; `installed` and `contract` are
host-owned inputs, not model output. `contract` is the actual authorized
NativeWorkflow task; `files` is `snapshot` of an isolated materialization of its
exact selected revisions. `workspace` must equal `worker.root / execution / "work"`.

```python
from native_proposal_adapter import installed_profile, build_request
from native_model_producer import prepare_inputs, register, source_digest
import runner
import evaluate

profile = installed_profile("heqi-native", installed)
# Real cases must carry actual admitted governance, original task and fixed paths.
report = evaluate.evaluate(profile, representative_cases, "live")
# Persist report as UTF-8. Attach profile.evaluation with report profile_digest,
# scope, passed_task_types, absolute evidence_ref and actual file SHA-256.
inputs = prepare_inputs(contract, execution, workspace, files,
                        ["module/file.txt"], "Exact independently checked acceptance")
# Use inputs as plan.task.input and execution as plan.task.id. agent_id comes
# from the actual admitted role, never from model output. One native proposal
# step uses a closed JSON schema with request_id, input_digest, summary, files.
plan["task"]["input"] = inputs
plan["profiles"] = [profile]
plan["limits"] = {"max_calls": 1, "max_output_tokens": None,
                  "output_token_limit": "unsupported"}
plan["central_budget"] = {"state_dir": str(central), "max_calls": admitted_calls,
                          "max_concurrent": admitted_slots, "authority_ref": mandate}
state = central / "tasks" / runner.jid_for(plan["task"])
# Persist plan then use existing runner.py authorize --plan ... --state ...
# --authority-ref ... --out ... . This binds source, framework and exact state.
grant = runner.read(grant_path)
register(registry, execution, grant, framework)
workflow.execute(actor, execution)  # Existing NativeWorker owns actual process.
```

`build_request(messages)` is the single public pure constructor used by transport:
it returns ordered original request, retained governance messages, and effective
request. Evaluate and execution use the same constructor. Effective context is
limited to 65536 UTF-8 bytes, task to 32768, acceptance to 16384, request ID to 128;
write paths use the existing ASCII portable proposal dialect (<=512 bytes,
<=64 paths). These limits are checked before model process launch, in addition
to the aggregate request/response limits above. Host role/capability admission
must be verified before calling evaluate with `scope="live"`; that label itself
is not independent proof of a real provider or permission.

### Ordinary installed runtime transport

Ordinary main can select local or existing RemoteNativeWorker execution through the digest-pinned runtime sidecar described in `design-docs/native-production-entry-20261118.md` (repository-root relative). Its context policy is served over `/native-context/{execution}` to the installed broker, and is never writable through the ordinary request API. Producer configuration may add `context_transport` with an HTTPS server origin and private absolute `token_file`; node configuration also sets an absolute existing `contract_registry` matching the producer's registry argument. The existing signed template must admit the context tool and call budget when demand context is selected. Small tasks retain bounded full inputs. Historical delta pairs require a separately admitted policy and are denied by this sidecar.

Server-owned context receipts are read only after real worker closure; node-local copies cannot establish current server authority. Transport or model outcomes that are unknown retain their original intent. Deterministic HTTP/node tests are not production model acceptance or a universal cost-saving measurement.

Local context admission continuation (#1501) retains the same serialized RPC,
execution and call identity inside the live tool turn. Only an exact HTTP 503
`not_started/context_capacity` response is retried, with at most 16 attempts,
a 120-second admission scheduling budget, and equal-jitter exponential delays
from 0.125–0.25 seconds up to 2–4 seconds. Each new attempt reserves the full
35-second transport window beyond the server's 30-second start deadline; no
shortened final attempt is sent. Socket timeouts remain unknown outcomes, not
proof of nonexecution. Exhaustion preserves `ContextNotStarted`. The caller's
existing model response remains in memory; no model call, execution, daemon or
persistent recovery job is created. Process interruption remains under the
outer worker's physical lease and cancellation control; each admitted request
rechecks current server authority and closure. This is bounded live admission,
not durable crash recovery or a guarantee that all 250 contenders complete.
