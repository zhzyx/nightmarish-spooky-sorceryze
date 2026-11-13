# Ordinary game task receipt storage recovery

<!-- gonggong-request:editor-game-receipt-storage-20261112 -->
<!-- gonggong-host-git:Sail-Li -->

Parent #773; related incident chain #807. Design: `design-docs/editor-game-receipt-storage-20261112.md` (repository-root relative).

During actual editor game production, an authorized command moved untracked baseline collisions to a private backup before a normal fast-forward. It also moved `work-items.json` and `gonggong-diting-data/dataset.json`. Tool-end receipt flushing failed before the next command could restore or advance the workspace. Exact original files were recovered from a verified private backup, and the editor subsequently completed the fast-forward. No game implementation or receipt result was fabricated.

Source audit: native provenance wrapping currently depends on an engine candidate; ordinary game tasks do not have one. The existing guard also does not capture work-items.json, and resolving a new binding requires that file. Source metadata protection must be available for ordinary game commands without manufacturing an engine candidate.

Acceptance:
- [ ] Ordinary game commands capture the minimum host-validated receipt/binding metadata needed for recovery in private storage outside mutable command paths, scoped to the actual workspace, requirement and operator.
- [ ] On missing metadata, recover only trusted missing originals before recording the tool result; preserve changed files/conflicts, foreign workers, queue history and original command diagnostics. Never silently replay commands or forge authority/events.
- [ ] Legitimate one-command fast-forward/configuration updates remain possible; availability protection must not turn arbitrary configuration bytes into immutable source governance.
- [ ] Regression tests cover an ordinary task without engine_candidate, missing dataset and work-items, failed/canceled command paths, changed-file conflicts, invalid/symlink boundaries and legitimate fast-forward. Run relevant native integration to verify flush/next-step behavior.
- [ ] Independent review, formal gate, exact CI/main, installed consumer verification and original failure-flow recovery are recorded. Parent #773 remains incomplete.

Authorization: current user's continuous Godot editor completion goal, including necessary editor lifecycle and automatic delivery. Current root owns recovery/delivery; preserve other workers and private evidence. No frozen framework/Agent definition changes.


Placement: extend existing native command boundaries and the trusted host Python provenance tool. The new native implementation unit is `editor/docks/receipts/GameReceiptGuard.cpp`, explicitly compiled by `editor/docks/SCsub`; its build classification, host contract and rollback are recorded in `editor/docks/receipts/build-impact.json`. The guard Python entry runs as a separate process from the trusted engine root. Native changes require a rebuild; install the matching trusted host tools. Roll back to the previous verified installation while retaining recovery records and projects. Do not weaken engine-candidate provenance.

Implementation: ordinary tasks receive a separate `game_receipts` binding from the host-validated reporting scope (workspace, Git common directory, Issue source, request, tenant and actor). It is never an `engine_candidate`. The private storage root is the absolute host `LOCALAPPDATA/gonggong-game-receipt-bindings` path on Windows, or the host user's `.local/share/gonggong-game-receipt-bindings` fallback; it must resolve outside the mutable workspace. Relative evidence paths below resolve from this repository root.

Only `work-items.json` and `gonggong-diting-data/dataset.json` are captured for ordinary-task availability. Missing files are restored with exclusive creation; present files are never overwritten. Repository/tenant/dataset identity and dataset structure must remain valid, while legitimate nonidentity configuration changes update the recovery baseline. Other workers, event history and queue files are untouched. Existing engine provenance rules retain their stricter behavior. API/native command launch, CLI approval, pre-flush recovery and exact command-journal cold recovery all use the ordinary binding. Cold recovery retains the original command invocation hash and never replays commands.

Validation scope: disposable Python Git/process fixtures cover normal/failed/cancelled commands, missing settings before recovery, configuration identity conflicts, legitimate fast-forward, foreign history, exact terminal recovery and Windows dataset/outbox/private/cold-read junction rejection. Windows file-symlink creation is unavailable without the host privilege; actual junction cases run without that privilege. The native cold restart fixture checks no candidate, one execution/result, queued-message preservation and a second crash-window replay. Raw attempts, including failures, are retained under `bin/948-validation/`; installed-consumer acceptance, final independent review and CI/main delivery remain owned by the root delivery session.

Independent source and evidence review of the final r2 candidate passed. The exact final input blobs, strict rebuild, static checks, original-flow fixture and cold recovery are recorded in `data-collection/editor-game-receipt-storage-948-r2.json`; the original report is preserved. Integration of current main `34498a33d500475a3538fb99a8e47dd516d2e5d1` changed no reviewed implementation bytes and retained the owned pre-integration stash. Formal delivery and installed-consumer replay remain pending; the checklist above is not marked fully accepted by local validation.
