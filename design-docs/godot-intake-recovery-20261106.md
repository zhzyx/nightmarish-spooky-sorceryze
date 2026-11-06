# Preserve intake failure reasons and bound transient read recovery

<!-- gonggong-request:godot-intake-recovery-20261106 -->

The user reported `Issue intake rejected` while following the live Godot
conversation for #165. A fresh read confirmed #165 is open, in progress, labelled
workspace:gonggong, and bound to the expected stable ID. Running the same intake
check passed. The earlier failure's stderr was discarded, so its cause remains
unknown; do not assert that it was an authentication or network failure.

Scope: expose safe, specific intake reasons and retain bounded subprocess stderr
in a private ignored diagnostic file. Retry only the read-only intake command,
once, for recognised network/timeout/HTTP 429 or 5xx failures, within the existing
120-second overall budget. Never retry authentication/permission/binding/status
rejections, fall back to stale approval, invoke a model, or replay an action.
Preserve the unfinished #165 edits and do not close #165.

Platform: macOS arm64; Python bridge only, no C++ build. Acceptance is focused
regressions for success, transient recovery, hard retry/budget bounds, permanent
rejections and private diagnostics; independent review; a real read-only intake
check using the active host environment; then normal Git delivery and readback.
