---
name: wenqu-doc-authoring
description: Author, version, classify and export Tianxuan Markdown documents with AI-readable structure.
---

Read the active document, workspace and authorization from the host. Keep Markdown as the only authoritative format; preserve frontmatter (`id`, `title`, `lang`, `kind`, `version`) and stable heading anchors.

Work in small, verifiable edits: resolve the current version first, refuse stale writes, and record the new version plus content hash. Build the AI view (headings, wiki links, summary, token estimate) from the same bytes you write.

Classify with rules first and a model second; never let a model result overwrite a human correction without an explicit change event. Export must round-trip to the same Markdown.

On conflict or unknown outcome, keep the original document and evidence, report the exact stage, and do not retry blindly.

Report through the shared Diting binding; queued is not recorded and recorded is not consumed.
