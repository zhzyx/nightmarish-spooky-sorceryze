# Preserve bracket pairing state during text iterator growth

Request: `editor-bracket-stack-growth-20261112`; parent #773. This is the separate follow-up identified during independent review of #902, whose original input acceptance is complete.

The existing ScriptIterator uses a small local bracket stack. On its first heap growth, `modules/text_server_adv/script_iterator.cpp` allocates new storage without copying prior entries. Later closing-bracket matching consumes those prior entries. This is source-confirmed; a runtime regression has not yet been demonstrated. Preserve that distinction and the original #902 evidence.

Scope: reproduce the pairing-state problem with a meaningful native regression, correct the existing storage transition, and check nested/mixed bracket and script behavior. Preserve the existing Unicode input and emoji regression. No unrelated text-server redesign, new engine module, external engine directory or change to production history. Rebuild the native editor; rollback restores the previous verified binary and retains projects and receipts.

Acceptance:

- [ ] A regression demonstrates incorrect old behavior or an invalid state at the storage transition and passes after the correction; include ordinary nesting and mixed scripts.
- [ ] Original #902 Unicode, substring and emoji regressions still pass; strict Windows native build and suitable native tests pass.
- [ ] Independent review, formal gate, exact CI/main and installed consumer verification are complete.
- [ ] Record actual evidence and limits; do not claim #773 complete.

Execution authority is the current user's ongoing Godot editor completion goal, tracked by #773. Current operator owns this isolated follow-up. Existing in-flight workers and unrelated worktrees remain with their owners.

Local native evidence is now recorded in `data-collection/editor-bracket-stack-916.json`.
The registered old regression failed at 128 outer brackets (2 script ranges,
expected 3); the correction passed 40 assertions across ordinary, first-growth
and subsequent-growth depths. The original #902 regression passed 38,629
assertions, and the full suite passed 1,569 cases / 474,354 assertions with
3 skips. Earlier zero-test and incorrect-fixture attempts remain explicitly
excluded from the growth reproduction claim. Test registration requires the
module's `tests=yes` build define; production builds exclude the test header.
Independent review, exact delivery and installation are separate remaining steps.
