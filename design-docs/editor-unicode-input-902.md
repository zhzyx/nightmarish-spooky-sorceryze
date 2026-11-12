# Preserve complete Unicode input during editor text layout

Request: `editor-unicode-input-crash-20261112`; [Issue #902](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/902), under #773.

The installed editor failed while laying out a long AI Chat input containing CJK, non-BMP emoji, quotes and long lines. The original input remains private. Later history inspection corrected the initial incident assumption: the message entered the paused durable queue before deferred layout failed; no model request or command execution occurred.

The existing native text server now converts span endpoints and returned boundaries in the correct coordinate space, preserves lazy substring spans, and allocates break inserts from current shaped clusters. ScriptIterator preserves emoji entries when growing its small buffer and retains storage across script runs. These are existing native engine inputs requiring a rebuild; no new module or runtime service is introduced. Rollback uses the previous verified editor binary and preserves project files and queued history.

Acceptance mapping:

- Original input preservation and layout: old installed engine fails; candidate TextEdit and RichTextLabel retain all 11361 characters and their byte hash, complete layout and wrap. Eight headless cases also cover short text, long CJK/emoji/quotes and combining/ZWJ content.
- Boundary repair: native tests cover multiple language spans, nonzero parent offsets, nested and tail substrings after reshape, and emoji storage growth across different scripts with exact glyph coverage.
- Native verification and independent review: strict Windows build, 1568 native cases / 474314 assertions, targeted regressions and independent read-only review pass. Historical failed and diagnostic-only attempts remain separate.
- Delivery and installed consumer: current-main integration, exact CI/main, official installation and actual editor ChatInput replay remain required. Local fixtures do not close this item or #773.

Public validation receipt: `data-collection/editor-unicode-input-902.json`, relative to the repository root. Raw logs and original input remain private. Headless results do not claim pixel rendering or interactive user acceptance. Existing native test diagnostics are retained.

Independent review also identified a pre-existing bracket-stack growth concern, which remains a separate investigation under #773. The long-command execution acceptance in #891 is distinct from input layout.
