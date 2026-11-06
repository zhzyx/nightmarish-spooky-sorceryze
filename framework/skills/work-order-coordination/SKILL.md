---
name: work-order-coordination
description: Coordinate Gonggong work orders when requests, progress, dependencies, decisions or execution receipts change; update progress documents and arrange needed work across all task types. Domain judgments stay with their owners.
---

# Work-order coordination

Use the shared Gonggong framework's project-state and work-order-management specifications for the current responsibility. Apply gonggong-check only when generating Agent or skill definitions; ordinary coordination does not trigger it. Reuse already loaded Yuanheng and foundation sources. This skill adds no agent identity, authority, ledger or automatic dispatch.

Resolve the host-selected process platform against runtime-ref.json. Run board to inspect source health, provenance and blockers; ready gives dispatch candidates, not authorization. Prioritize using the user's actual goals and delegated scope. Use business-appropriate task types and completion criteria; Feature links apply only when relevant. Keep delivery with its accountable owner and escalated quality oversight with Kuafu.

Use prepare only to build a handoff to the existing source CLI and host. It does not execute. Before a real transition, revalidate source versions, cross-ledger constraints, actual capacity and authority; never directly edit a source ledger or treat a host-pending assignment as executed. Unsupported source transitions remain pending adapter work.

Surface only a concrete reserved user choice or meaningful change in delivery. Keep source state, evidence health, coordination status and synchronization distinct. Do not infer that unregistered sources or inaccessible work are covered.

On a relevant event, follow specs/work-order-management.md: persist any authorized source transition through its original CLI, refresh progress documents through the bound refresh entry, and dispatch ready work only when needed. Reconcile actual worker receipts before releasing capacity. Independent ready work may run concurrently; metadata transactions stay short. Timers, polling, delayed wakeups and time-based retries are prohibited; without an event, do nothing. Follow reporting.json through shared Diting with a real host binding; queued is not delivered.

For a new request, have the host retain its source event and stable request identity, deduplicate at the authoritative source, create or link an authorized work item through that source, and read back its ID and version before `request.created` refresh or work that requires a ticket. An uncertain write requires reconciliation before retry. Writing to an external work-management source requires an explicitly bound adapter and a current mandate.
