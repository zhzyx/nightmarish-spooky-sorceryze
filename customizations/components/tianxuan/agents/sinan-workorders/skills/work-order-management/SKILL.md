---
name: sinan-work-order-management
description: Manage Tianxuan work orders: create trees from requirements, enforce transitions, and aggregate progress from events.
---

Read the requirement document, project template and authorization from the host. Create the parent issue plus independently deliverable children; every child carries an explicit acceptance and a stable ticket key.

Only apply transitions defined by the project state machine. On an illegal edge, reject and keep the current state; do not invent an intermediate state.

Aggregate progress from events, not from hand-edited counters. A requirement is accepted only when every mapped ticket has a live acceptance record; a child completion never closes the parent by itself.

Keep the document, issue and commit links bidirectional and readable. On unknown remote state, read back before retrying.

Report through the shared Diting binding; queued and recorded are different states.
