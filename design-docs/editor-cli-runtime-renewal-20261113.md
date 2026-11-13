# Restore the original editor production session after Windows CLI replacement

<!-- gonggong-request:editor-cli-runtime-renewal-20261113 -->

Parent: #773. The user authorized continuous completion of the Godot editor production workflow, including editor lifecycle and local tool configuration. This Windows acceptance session remains owned by the current root operator; no other worker installation or credentials are changed.

After installing verified main PR #1054, the original game history restored correctly, but its private runtime configuration referenced a removed Codex desktop package. The registered replacement package contains a working CLI; its version query succeeds. No production request was sent using the missing path. The earlier macOS cleanup/startup Issue #954 is a different installation and is not taken over.

Use the editor's existing public runtime-field configuration entry to select the verified replacement executable. Preserve backend, model, credentials, conversation identity, original producer terminals, queue and design confirmation. Do not reset the conversation by replaying the whole backend configuration flow. No new discovery policy or implicit authority is introduced.

Acceptance:

- The configured executable exists and its version query succeeds; changing the single runtime field is acknowledged by the actual installed editor.
- The same parent conversation and original production batch remain selected, with original terminal/candidate identities preserved and never-started dependents still unexecuted.
- Actual editor model discovery or request validation consumes the corrected runtime. The original parent can request production status through the product entry without external edits to game code or receipts.
- Record the observed environment failure, correction and consumer evidence, with independent verification and normal evidence delivery. Keep parent #773 and unrelated remaining acceptance open.

Private absolute paths, account configuration, history and command acknowledgments remain in the owning host's receipts directory. Repository paths resolve from the repository root. Rollback retains the original configuration backup and history; an unavailable old executable is not represented as usable.
