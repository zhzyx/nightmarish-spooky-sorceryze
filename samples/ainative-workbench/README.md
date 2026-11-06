# AINative Workbench (Godot 4)

This is a local import / byte-copy demonstration, **not AI generation**. Open `project.godot` in Godot and select the **AINative** bottom panel, or run the standalone main scene. No C++ rebuild is required.

Install elsewhere by copying `addons/ainative` into the target project and enabling the plugin in Project Settings. Keep the repository's `tools/ainative` Python modules together in a trusted local directory; set the panel's Python executable and absolute `editor_host.py` path, then Save local settings. Python 3.11+ is required. The default sample path is resolved against this project's `res://`, not the shell working directory.

1. Add/select a copy node. Enter absolute source and optional image-context paths, text context, and JSON parameters (`{"delay":2,"fail":false}`). Apply selected fields. Connect output to another node's input by dragging ports; disconnect using the graph UI. Delete selected removes its edges.
2. Save/Open a `.json` workflow. Positions, edges, parameters and context persist. Source paths are local references; Run snapshots their bytes. Keep credentials out of text and parameters. There is no credential input; known credential/config keys are rejected. Trusted Python/script/factory settings remain only in `user://ainative/local.cfg` and are never loaded from graph JSON.
3. Run uses subprocesses and real SQLite Executor states. Cancel persists cancellation; Retry selected retries only a confirmed provider failure. The demonstration `fail:true` fails again after retry by design. Change parameters and Run to create a new run. Resume run resumes the last saved run; unknown submission outcomes pause after one lookup and require another explicit Resume, never blind resubmission.
4. Preview a selected successful node's PNG/JPEG or embedded GLB/glTF result. Mesh camera frames its bounds. Review & publish requires a current preview and explicit confirmation. Choose a new absolute `.tres` image or `.tscn` mesh filename; its parent must exist. Existing paths, including symlinks, fail closed. The displayed run, artifact token and encoded file SHA256 bind confirmation. Publication uses the contract's atomic no-clobber hardlink operation; unsupported filesystems fail without overwriting.

`fixtures` contains an actual 2×2 PNG and small triangle glTF/GLB. These are local synthetic sample assets, not model outputs. glTF and GLB with external buffers/images are rejected; embed dependencies first. The graph surface currently has one typed source/result port and a JSON parameter editor, with local-copy as the default definition. A trusted factory may register compatible one-source/result nodes/providers; this is the integration point for #145, not a general node-palette implementation. Large file decoding and Godot Resource/Scene serialization are synchronous Godot operations; remote execution and every Python command run outside the editor main thread. Very large previews can briefly pause the UI. No animation/rig validation is claimed.

On plugin unload, owned host processes are terminated; SQLite retains durable intent. Reopen and Resume to reconcile a pending run. A remote job is not claimed cancelled merely because the editor closed. Failed runs, cancellations and publication errors leave source assets intact. Runtime files live in Godot `user://ainative` (project-specific OS user data); successful test runs use unique `user://test-*` folders.

Validation (PowerShell, repository root):

```powershell
$env:AINATIVE_PYTHON = 'C:/path/to/python.exe'
& $env:AINATIVE_PYTHON -m unittest discover -s tools/ainative -p test_editor_host.py -v
& 'C:/path/to/godot.exe' --headless --editor --path samples/ainative-workbench --quit-after 10
& 'C:/path/to/godot.exe' --headless --path samples/ainative-workbench --script acceptance.gd
# Optional real-renderer screenshot, saved to acceptance-preview.png:
& 'C:/path/to/godot.exe' --path samples/ainative-workbench --script acceptance.gd -- --capture
```

Acceptance replay invokes the same panel methods and actual subprocess host, confirms the dialog programmatically for the test only, loads real images/meshes and reloads published resources/scenes. It is behavior evidence, not a claim that a person approved the test assets for production.
