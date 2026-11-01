---
name: ariadne
description: Coordinate Olympus work orders when requests, progress, dependencies, decisions or execution receipts change; update progress documents and arrange needed work across all task types. Domain judgments stay with their owners.
---

# Work-order coordination

Use the shared Olympus framework's dike, project-state and work-order-management specifications for the current responsibility. Reuse already loaded Zeus and foundation sources. This skill adds no agent identity, authority, ledger or automatic dispatch.

Resolve the registered sources and coordinator entry in runtime-ref.json. Run board to inspect source health, provenance and blockers; ready gives dispatch candidates, not authorization. Prioritize using the user's actual goals and delegated scope. Use business-appropriate task types and completion criteria; Feature links apply only when relevant. Keep delivery with its accountable owner and escalated quality oversight with Themis.

Use prepare only to build a handoff to the existing source CLI and host. It does not execute. Before a real transition, revalidate source versions, cross-ledger constraints, actual capacity and authority; never directly edit a source ledger or treat a host-pending assignment as executed. Unsupported source transitions remain pending adapter work.

Surface only a concrete reserved user choice or meaningful change in delivery. Keep source state, evidence health, coordination status and synchronization distinct. Do not infer that unregistered sources or inaccessible work are covered.

On a relevant event, follow specs/work-order-management.md: persist any authorized source transition through its original CLI, refresh progress documents through the bound refresh entry, and dispatch ready work only when needed. Reconcile actual worker receipts before releasing capacity. Independent ready work may run concurrently; metadata transactions stay short. Timers, polling, delayed wakeups and time-based retries are prohibited; without an event, do nothing. Follow reporting.json through shared Hermes with a real host binding; queued is not delivered.

The framework root is ../.. relative to this skill. runtime-ref.json paths are framework-root relative. Use the shared Hermes reporting.json; the file-data exemption remains available. External source ledger format .yuanheng/state.json is preserved. No live sources or CLI are bound by default.
