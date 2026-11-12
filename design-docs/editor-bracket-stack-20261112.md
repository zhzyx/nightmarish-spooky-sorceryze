# Preserve bracket pairing state during text iterator growth

Request: `editor-bracket-stack-growth-20261112`; parent #773. This is the separate follow-up identified during independent review of #902, whose original input acceptance is complete.

The existing ScriptIterator uses a small local bracket stack. On its first heap growth, `modules/text_server_adv/script_iterator.cpp` allocates new storage without copying prior entries. Later closing-bracket matching consumes those prior entries. This is source-confirmed; a runtime regression has not yet been demonstrated. Preserve that distinction and the original #902 evidence.

Scope: reproduce the pairing-state problem with a meaningful native regression, correct the existing storage transition, and check nested/mixed bracket and script behavior. Preserve the existing Unicode input and emoji regression. No unrelated text-server redesign, new engine module, external engine directory or change to production history. Rebuild the native editor; rollback restores the previous verified binary and retains projects and receipts.

Acceptance:

- [x] A regression demonstrates incorrect old behavior or an invalid state at the storage transition and passes after the correction; include ordinary nesting and mixed scripts.
- [x] Original #902 Unicode, substring and emoji regressions still pass; strict Windows native build and suitable native tests pass.
- [x] Independent review, formal gate, exact CI/main and installed consumer verification are complete.
- [x] Record actual evidence and limits; do not claim #773 complete.

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

Main PR924 introduced the new C++ coding standard before delivery. The new test
now resides in `internal_tests/TestScriptIterator.h`, with a directory-scoped
formatter override and unchanged assertions. An initial placement in `tests`
failed strict compilation because automatic test collection lacks the module
private includes; that attempt is retained. The corrected strict build and
both affected regressions pass (2 cases / 38,669 assertions), and bracket-only
execution confirms 1 case / 40 assertions with no duplicate registration.
Independent read-only review verified the actual regenerated header, all native
inputs, logs and binaries. Additive evidence is
`data-collection/editor-bracket-stack-916-main924.json`. Exact new CI/main and
installed consumer acceptance remain pending; preceding evidence is unchanged.

PR930 header-guards rejected a comment before `#pragma once`. The comment
was moved below the guard without semantic change; the corresponding guard,
copyright, file-format and clang-format checks now pass. Main PR928 was
integrated without conflicting writes, and the combined candidate strictly
rebuilt and passed the two affected regressions. Independent comment-only
review found no new issue. Additive evidence:
`data-collection/editor-bracket-stack-916-guard.json`. New exact CI and installed
acceptance remain required.

PR932 passed applicable exact CI including Windows Editor and merged to
`23412df4cff43f3579adb90524a396d2a4b9e82f`. The clean-main official build
passed 90 AIChat cases / 1,672 assertions and was installed. Installed native
regressions passed 2 cases / 38,669 assertions; TextEdit and RichTextLabel each
passed the four-case mixed-bracket and original Unicode input scenarios, with
binary and input hashes preserved. See
`data-collection/editor-installed-main932-773.json`. Parent773 remains open.
