# Preserve user corrections across requirements intake

<!-- gonggong-request:requirements-context-user-corrections -->

Issue: [#184](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/184).

Related: #165 (active product work), #166 (earlier conversation-context integration).

The user asked Codex to follow the running editor conversation and prevent repeated
clarification loops. Inspection found that `_begin_issue_agent` selects only the
newest 32 visible user/editor/assistant records. Environment setup, progress and
repeated retry records can consume that window and remove earlier explicit user
corrections while those corrections remain in the unchanged local history.

Scope: select a bounded requirements conversation that prioritizes original user
statements and keeps necessary question/answer context in chronological order.
Define duplicate and retry-control handling without inferring product decisions.
Keep the existing 32-record, 16000-character and 4000-character-per-record limits.
Do not summarize user authorization, hard-code feature values, change the stored
conversation, or modify the CLI/model feature work being implemented in #165.

Platform: macOS arm64. Use the production C++ selector directly in native tests;
verify the affected C++ translation unit using the established side-by-side
build workflow without replacing, restarting or stopping the running editor.
The parent Codex session owns independent review and any later integration.

Acceptance:

- Older explicit user corrections survive a long run of editor setup/progress
  messages and repeated transport retry messages when they fit the stated limits.
- The latest actual user answer and its preceding question remain available;
  retained records keep their exact original roles/text (apart from bounded excerpts)
  and actual chronological order. No domain-specific preference is inferred.
- Record and character budgets remain enforced; unsupported/empty records and
  duplicate handling are deterministic, without semantic deduplication of user turns.
- Retry reconciliation continues to reuse the original captured conversation.
- Existing #165 edits, live engine state, user history and approval records remain intact.

Selection contract: reserve the newest actual user statement and its closest
preceding visible reply before other records, then keep older user statements,
then their preceding replies if room remains. Only user turns that the host
actually consumed as an `agent_error` intake retry carry the boolean
`requirements_transport_retry` metadata; only those marked turns are lower
priority and collapse to the newest one. Legacy/unmarked records remain user
statements regardless of wording, including literal `重试`/`retry` answers to
questions about UI text. Repeated identical answers to different questions are
never semantically deduplicated. Return retained records in their original order.
Metadata is local context-selection information, is not sent as user text, and
does not authorize any operation. The fixed budget cannot preserve an unlimited
history.

Existing retry reconciliation deliberately reuses its captured context to keep
the same requirement journal identity. This selector applies when a new intake
context is captured; it does not rewrite an earlier attempt or the conversation.

Final parent integration: combined with #212 on main `491888459dbb64c8130378d8dbb3649cc1fd6ac8`. The latest native build and all five context cases / 207 assertions exited successfully; the final six-source combination received independent read-only review without blocking findings. See the [append-only final integration record](../data-collection/restart-context-main491888-integration-validation.json). The earlier e9dd evidence remains historical; live #165 source and the user conversation were not rewritten by this context contribution.

The final signing baseline advanced to `ab029a263c88c415fbcf648b4d505f18f85885c4` after concurrent PR #223. The exact combined source inputs were incrementally rebuilt and both native suites passed again; the additional integration delta received independent read-only review. The [final parent acceptance](../data-collection/restart-context-mainab029a-integration-validation.json) supersedes the earlier baseline for submission. Primary PR association remains #212; #184 retains separate formal gate and acceptance.
