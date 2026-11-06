# Codex action argument transport recovery

<!-- gonggong-request:codex-action-arguments-20261106 -->

User reported `Codex returned invalid JSON or an invalid action` while the Godot
conversation was implementing Issue #165. The failed model response was not
retained, so its exact syntax error is unknown. Earlier successful operations and
the unfinished #165 changes must remain intact.

Scope: remove unnecessary nested JSON encoding for tools with closed, typed
parameter schemas; bind the response schema to the current allowed tools. Keep
legacy string arguments for dynamic editor operations and old responses. Reject
malformed/forbidden batches in full, with bounded non-sensitive diagnostics and
no automatic model retries or action replay. This repairs the local bridge; it
does not complete or close #165 and does not alter its model-picker work.

Validate with focused offline protocol regressions, one read-only real CLI format
check on macOS arm64, independent review, and the repository delivery checks.
No C++ changes or engine rebuild are needed. Apply only the recovery patch to the
active workspace after preserving its unfinished changes. Stop on an actual
permission/admission failure; retain all evidence and the reviewable candidate.

Acceptance:

- Typed tool arguments with newlines, quotes and backslashes survive transport.
- Only currently allowed tools appear in the generated output schema.
- Optional arguments keep host defaults; explicit required/null values are not
  silently discarded.
- Invalid batches never produce partial tool calls; diagnostics contain no
  model text, commands, paths or secrets; no automatic retry is introduced.
- Existing CLI image handling, consultation restrictions and legacy responses
  continue to work; #165 edits remain intact.
