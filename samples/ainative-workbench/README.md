# AINative Workbench (Godot 4)

The workbench supports local import/copy and four ComfyUI generation nodes: text to image, image to image, image to Mesh, and text to Mesh. Copy remains the default offline demonstration and performs no AI inference. Real generation requires the separately installed backend and trusted local configuration described in [the provider guide](../../tools/ainative/README.md). Open `project.godot` in Godot and select the **AINative** bottom panel, or run the standalone main scene. No C++ rebuild is required.

Install elsewhere by copying `addons/ainative` into the target project and enabling the plugin in Project Settings. Keep the repository's `tools/ainative` Python modules together in a trusted local directory; set the panel's Python executable and absolute `editor_host.py` path, then Save local settings. Python 3.11+ is required. The default sample path is resolved against this project's `res://`, not the shell working directory.

1. Add/select a copy node. Enter absolute source and optional image-context paths, text context, and JSON parameters (`{"delay":2,"fail":false}`). Apply selected fields. Connect output to another node's input by dragging ports; disconnect using the graph UI. Delete selected removes its edges.
2. Save/Open a `.json` workflow. Positions, edges, parameters and context persist. Save embeds input bytes and their hashes, omitting local paths; Run also snapshots any newly selected files. Clear embedded source/context explicitly when removing a reopened reference. Keep credentials out of text and parameters. There is no credential input; known credential/config keys are rejected. Trusted Python/script/factory settings remain in process environment or `user://ainative/local.cfg` and are never loaded from graph JSON.
3. Run uses subprocesses and real SQLite Executor states. Cancel persists cancellation; Retry selected retries only a confirmed provider failure. The demonstration `fail:true` fails again after retry by design. Change parameters and Run to create a new run. Resume run resumes the last saved run; unknown submission outcomes pause after one lookup and require another explicit Resume, never blind resubmission.
4. Preview a selected successful node's PNG/JPEG or embedded GLB/glTF result. Mesh camera frames its bounds. Review & publish requires a current preview and explicit confirmation. Choose a new absolute `.tres` image or `.tscn` mesh filename; its parent must exist. Existing paths, including symlinks, fail closed. The displayed run, artifact token and encoded file SHA256 bind confirmation. Publication uses the contract's atomic no-clobber hardlink operation; unsupported filesystems fail without overwriting.

For generation, launch with `comfy_provider:factory`, choose a kind beside **+ Generate**, and add the node. Set JSON parameters such as `{"prompt":"a stone owl on white background","seed":42}`; image nodes require a source image or connected image output. Optional text and one total reference image are supported. Source plus an additional image is explicitly unsupported by this backend. Text to Mesh composes image generation with Hunyuan3D; Mesh output is currently untextured geometry. See the provider guide for parameters and backend setup.

Open `four-flows.json` for a ready graph: a generated robot image feeds image editing and Mesh generation, alongside a text-to-Mesh helmet node. It contains prompts and links; generated assets remain in the configured local run store until you preview and publish them. Running it requires the real backend.

`fixtures` contains an actual 2×2 PNG and small triangle glTF/GLB. These are local synthetic sample assets, not model outputs. glTF and GLB with external buffers/images are rejected; embed dependencies first. The graph surface uses typed source/result ports and a JSON parameter editor. Large file decoding and Godot Resource/Scene serialization are synchronous Godot operations; remote execution and every Python command run outside the editor main thread. Very large previews can briefly pause the UI. No animation/rig validation is claimed.

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

`live_acceptance.gd` separately replays actual generated runs. Pass a JSON array containing `kind`, `run_id`, absolute Executor `db`, and extracted artifact `file` for all four kinds. Set `AINATIVE_PYTHON` and `AINATIVE_COMFY_CONFIG` for the same deployment. Run `--script live_acceptance.gd -- D:/runtime/live-runs.json`; optionally append an existing capture directory when using a real renderer. This checks successful Executor receipts, exact image pixels, nontrivial Mesh geometry, confirmation before publication, resource reload, and preservation of the original generated bytes. It does not generate or substitute test assets.

`live_generate.gd` exercises actual generation through the panel after saving and reopening a workflow with both text and image context. With the same environment and a running backend, invoke `--script live_generate.gd -- D:/reference.png D:/runtime/new-context-receipt.json D:/runtime/context-preview.png` (the screenshot argument is optional). The receipt must not already exist. It checks actual inference, editor heartbeat, integer parameter transport, context use, source preservation and preview. This consumes local GPU inference resources.

The first local model validation produced all four formats and passed Godot publication/reload. Raw meshes still require inspection: the robot has a residual base and the thin-shell helmet has holes. Neither successful generation nor preview certifies production topology or animation readiness; normalization and rigging belong to the next stage.

After previewing a generated Mesh, the Character panel offers anatomical template fitting, explicit cleanup, joint/weight correction, skeleton preview and three ROM clips. Standard mode requires a suitable T-pose humanoid; free mode requires the complete anatomical landmarks and can declare a manually marked source pose. Save a new character version and reopen its source-bound corrections. See [the rigging design and limits](../../design-docs/ainative-art/05-rigging.md). The workbench scrolls to keep controls accessible in smaller windows.

`rigging_acceptance.gd -- source.glb new-character.tscn params.json` checks actual Skin/rest, weights, three animated deformations and sampled squat foot contact. `rigging_live_ui.gd -- live-runs.json params.json new-preview.png new-receipt.json` uses the same deployment environment as `live_acceptance.gd` to replay a real `image_to_mesh` output through fitting, publication, no-overwrite and reopen operations. The latter invokes actual panel methods and requires new screenshot/receipt paths; its confirmation is test-only. Neither script invokes an AI model.
