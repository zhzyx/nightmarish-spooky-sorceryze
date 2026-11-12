# Ordinary review failure return (#899)

Parent: #773. Fault chain: #807. Authorization and acceptance source:
https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/899

The native ordinary-game reviewer may finish with a failed source read. Its
report and durable host receipts must reach the still-authorized parent as
diagnostics so the parent can repair or repeat the review. A diagnostic never
establishes business acceptance.

The existing design-batch parent queue remains the only return path. Failed
read_file/read_script callbacks retain their redacted host error and original
result digest and set review_source_unverified. The parent envelope labels the
review source_unverified or report_only, with business_accepted=null. A failed
read remains present in counters and first_unverified_receipt even if the
bounded receipt window rolls over.

Only ordinary-game review can return source-unverified diagnostics. Existing
successful-read byte/link checks, candidate HEAD/root/branch/base binding,
parent snapshot and current authority guards still gate queue consumption.
Engine review and automatic independent acceptance retain their rejection of
source-unverified review. Cold state cannot recreate a live return capability.

Native tests use an isolated ordinary game with controlled model transport and
real editor dispatch, read tools, receipt persistence, and parent continuation.
The missing-read flag can accompany candidate-drift and revocation scenarios;
normal and missing-read runs also restore the editor to verify no replay.
The reported fixture acceptance concerns these behavioral assertions only.
It does not accept the original game, #773, or the independent review itself.

This changes an existing native module, with ai_chat_sub_agents.cpp as the
compiled input. Rebuild the editor for deployment or rollback; no new runtime
module or host interface is introduced. Installed real-project revalidation,
independent review, exact-candidate CI and main delivery remain the parent
session's responsibility.

Installed main `3a714a6d6b337e47f1047c6af2342ca05c956a08` now has an
actual-provider observation in
`data-collection/editor-review-failure-return-899-installed.json`: review 15
retained two failed reads and 133 tool receipts, returned once with
`source_unverified` and no business approval, and the parent automatically
continued candidate checks and the formal local gate. An independent host
readback verified all 66 successful source hashes and the returned receipt
reference. The separate private Issue binding mismatch remains explicit;
this result does not approve the original game's candidate or close #773.
