---
name: sinan-work-order-management
description: Manage the Tianxuan work-order model, legal transitions and event-derived progress without duplicating core coordination.
---

Read the work-order context, project template and authorization from the host. Operate on already-created source tickets; creation, dispatch, dependency coordination and acceptance are owned by core 司南, the hosting source and authorized acceptors.

Apply only transitions defined by the project state machine. On an illegal edge, reject and keep the current state; do not invent an intermediate state.

Aggregate progress from events, not from hand-edited counters. Do not decide whether a requirement is accepted.

Keep document, issue and commit links bidirectional and readable. On unknown remote state, read back before retrying.

The host authenticates identity, tool permission and actual authority; this skill grants no execution authority and cannot approve its own admission. Report through the shared Diting binding; queued and recorded are different states.
