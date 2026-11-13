# Make editor production design format discoverable and failures actionable

Request: `editor-design-contract-20261112`; parent #773. Paths in this document resolve against this repository root.

The actual installed editor generated a detailed new game requirement with `## 4. 生产工单` and `### 工单 A/B/C`, without the exact confirmation heading. The native production parser requires `## 生产工单`, top-level numbered items, explicit dependencies and a recognized confirmation section. Current model guidance documents criterion lines but omits this structural contract. The generic failed-design message does not identify the missing section or usable repair. Source review confirmed this mismatch; the current game design is being corrected through ordinary editor chat and remains unapproved.

Scope: make the existing exact parser contract available in the model design guidance, supply concise actionable diagnostics for malformed designs, and preserve explicit native design confirmation and dependency authorization. Do not relax governance, infer approval from document text, accept arbitrary Markdown, alter other workers or modify the private game from this worktree.

Acceptance:

- [x] Model design guidance includes the actual confirmation heading, production section, numbered work orders, independent/dependent examples and unique criterion IDs. The template clearly remains pending native user confirmation.
- [x] Actual parser/read-design diagnostics distinguish missing confirmation, missing production section, no numbered work orders and invalid dependencies, with practical correction hints. Existing valid designs remain accepted; malformed dependencies remain rejected.
- [x] A meaningful native regression exercises the observed natural Markdown forms and verifies diagnostics, valid template parsing and retained confirmation boundaries. Appropriate existing design/acceptance tests and a strict Windows editor build pass.
- [x] Independent review, formal delivery, exact CI/main readback and installed consumer verification are recorded. A corrected game design or this bug fix does not complete parent #773.

Local validation evidence: `data-collection/editor-design-contract-943.json` preserves the initial candidate; `data-collection/editor-design-contract-943-format.json` records the final format-compatible candidate. The final strict Windows build, 93 native test cases (all 1718 assertions retained) and isolated design button diagnostics/manual dependency flow passed. Native independent acceptance passed on the preceding candidate; unchanged acceptance behavior is covered by final native parser tests and design consumption. Failed fixture and static-check attempts remain recorded. Model output quality and installed consumer behavior are not inferred from fixtures; formal delivery and installed verification remain with the root owner.

Placement: native changes to existing editor C++ prompt/parser/UI code; no new module. Rebuild affected native inputs. The interface remains normal chat plus the existing work-order production button and confirmation dialog. Rollback restores the prior verified editor binary while retaining projects, designs and all receipts.

Authorization: current user's continuous Godot editor completion goal under #773. Root owns delivery and live consumer validation; an isolated implementation worker may change only this worktree, with a separate reviewer. Preserve failures and distinguish source findings, fixture results and actual live editor observations.

Installed validation: PR #947 merged as `d91bd93eb14d1420db9e6872c638e9cb82baf015` after exact-candidate CI. A clean main build passed 90 AIChat cases / 1707 assertions. The formally installed editor passed the design-consumer fixture, including actionable malformed-design diagnostics, native confirmation boundaries and dependency handoff. `data-collection/editor-design-contract-943-installed.json` records exact hashes and transport limits. This does not complete parent #773 or claim live model output quality.

A supplemental exact shared-template UI probe passed native confirmation, both order titles/document hash, pending/cancel no-dispatch and the original fixture checks. Its initial unsupported dialog assertion and wrapper return-code error remain recorded in `data-collection/editor-design-contract-943-template-installed.json`. The method learning overclaim was counterexampled; the revised method remains a candidate for a future planned trial.
