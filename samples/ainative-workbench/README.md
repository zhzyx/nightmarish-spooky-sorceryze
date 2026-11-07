# 马良工作台（Godot 4）

马良是此引擎内置的编辑器页面。用当前构建打开任意工程，点击顶部 **AI Chat 右侧的“马良”** 即可进入，无需安装或启用工程插件。马良占满工作区，进入时隐藏场景树、检查器、场景标签和底部面板，切回 2D、3D 或脚本页面时恢复编辑器布局；旧版 AINative 标签顺序在恢复布局时自动迁移，并保留原选中页面。

页面提供 **网格生成、骨骼绑定、角色工作台、其他工具、本机设置**，默认打开网格生成。按钮、输入提示、确认与状态使用中文，ComfyUI、Python、GLB、UE4、Mixamo 等专名及 JSON 字段保留。生成选项通过 metadata 使用原英文类型，已有工作流与本机数据路径不变。先预览生成的网格，再切到骨骼绑定；也可在骨骼绑定页浏览本地网格。真实生成仍需配置模型服务，离线复制节点仅用于演示。外部工具的原始失败详情保留在本机诊断日志，可从“本机设置”打开。

The built-in native plugin embeds the shared workbench scripts and Python tools into the editor binary and installs a content-versioned bundle in editor data on first use. The default local host follows the current engine bundle when upgrading; explicit custom host settings are retained. Task state and settings are isolated by the absolute project path, outside project source. The sample below remains a standalone/regression harness and compatibility addon for older engines; on current engines its addon does not register a duplicate panel. See [the built-in entry and acceptance scope](../../design-docs/ainative-engine-builtin-20261107.md).

**Character Workbench** edits one shared character: body/face shape, independent clothing, animation layers and handheld equipment, captured face animation, cloth, and hair. Choose **角色工作台**, select the trusted local character recipe, then edit, save a new complete version, and reopen it. Sources, model weights, and machine paths remain local. See [the integrated workflow and acceptance limits](../../design-docs/ainative-art/13-integration.md) for recipe fields and the verified sequence.

Complete Godot `.tscn` publications retain all integrated components and can replay without the original source files. In built-in mode, characters with runtime scripts publish a sibling `.ainative-*` runtime directory: move this directory together with the scene when moving to another project. It contains runtime scripts, no editor plugin. Plain Mesh and rigging scenes need no such directory. Re-editing requires matching source locators. UE4, Manny and Mixamo GLB compatibility copies carry main-skeleton Skin geometry, static morphs and baked final body animation; their reports explicitly exclude the simulated skirt surface, independent hair, rigid props, face animation and runtime solvers. Quinn remains unvalidated in #202. This is a technical first version with documented source-quality and performance limits.

The generation graph and rigging have direct navigation on the built-in page; other individual modules are under **其他工具**. In the standalone sample and older editor addon, these are under **Advanced independent module diagnostics**. Their standalone panels do not share the current integrated character.

The workbench supports local import/copy and four ComfyUI generation nodes: text to image, image to image, image to Mesh, and text to Mesh. Copy remains the default offline demonstration and performs no AI inference. Real generation requires the separately installed backend and trusted local configuration described in [the provider guide](../../tools/ainative/README.md). Use the built-in **AINative** top workspace page; run this sample's main scene only for the standalone harness.

Set a trusted Python 3.11+ executable under **本机设置**, then Save local settings. The built-in `editor_host.py` and sibling Python modules are already supplied by the engine. The source-relative host path is used only by the standalone sample or legacy addon, resolved against that sample's `res://`, not the shell working directory.

1. Add/select a copy node. Enter absolute source and optional image-context paths, text context, and JSON parameters (`{"delay":2,"fail":false}`). Apply selected fields. Connect output to another node's input by dragging ports; disconnect using the graph UI. Delete selected removes its edges.
2. Save/Open a `.json` workflow. Positions, edges, parameters and context persist. Save embeds input bytes and their hashes, omitting local paths; Run also snapshots any newly selected files. Clear embedded source/context explicitly when removing a reopened reference. Keep credentials out of text and parameters. There is no credential input; known credential/config keys are rejected. Trusted Python/script/factory settings remain in process environment or `user://ainative/local.cfg` and are never loaded from graph JSON.
3. Run uses subprocesses and real SQLite Executor states. Cancel persists cancellation; Retry selected retries only a confirmed provider failure. The demonstration `fail:true` fails again after retry by design. Change parameters and Run to create a new run. Resume run resumes the last saved run; unknown submission outcomes pause after one lookup and require another explicit Resume, never blind resubmission.
4. Preview a selected successful node's PNG/JPEG or embedded GLB/glTF result. Mesh camera frames its bounds. Review & publish requires a current preview and explicit confirmation. Choose a new absolute `.tres` image or `.tscn` mesh filename; its parent must exist. Existing paths, including symlinks, fail closed. The displayed run, artifact token and encoded file SHA256 bind confirmation. Publication uses the contract's atomic no-clobber hardlink operation; unsupported filesystems fail without overwriting.

For generation, launch with `comfy_provider:factory`, choose a kind beside **+ Generate**, and add the node. Set JSON parameters such as `{"prompt":"a stone owl on white background","seed":42}`; image nodes require a source image or connected image output. Optional text and one total reference image are supported. Source plus an additional image is explicitly unsupported by this backend. Text to Mesh composes image generation with Hunyuan3D; Mesh output is currently untextured geometry. See the provider guide for parameters and backend setup.

Open `four-flows.json` for a ready graph: a generated robot image feeds image editing and Mesh generation, alongside a text-to-Mesh helmet node. It contains prompts and links; generated assets remain in the configured local run store until you preview and publish them. Running it requires the real backend.

`fixtures` contains an actual 2×2 PNG and small triangle glTF/GLB. These are local synthetic sample assets, not model outputs. glTF and GLB with external buffers/images are rejected; embed dependencies first. The graph surface uses typed source/result ports and a JSON parameter editor. Large file decoding and Godot Resource/Scene serialization are synchronous Godot operations; remote execution and every Python command run outside the editor main thread. Very large previews can briefly pause the UI. These graph fixtures do not validate animation or rigs; character acceptance is recorded separately in the integration design.

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

## 逐节点运行与预览

节点上的“运行并预览”只执行该节点及其必要上游，成功后自动展示图片或网格。不运行后续节点或无关分支；相同输入沿用执行器缓存。修改提示词、参数或参考图后再次点击才会生成，运行中重复点击不会重复提交。

右侧“本次会话版本”可切换该节点先前成功的预览，悬停查看当次参数；失败和取消保留已有版本。切换节点时分别显示各自结果。历史仅在当前工作台会话保留，打开另一个工作流会清空；运行途中先完成或取消，再打开工作流。预览不等于发布，发布仍需原确认步骤及整个对应运行成功。

后台回归：设置 `AINATIVE_PYTHON` 后使用 `--headless --path samples/ainative-workbench --script node_preview_acceptance.gd`。该回归使用离线复制服务，不调用模型。

## 右键优先的工作流编辑

在空白画布右键选择“添加节点”，可按图像、网格、离线工具分组或搜索；节点会出现在右键位置。右键节点可编辑提示词与参数、运行并预览、查看成功结果与本次会话历史、重试、复制或删除。右键连线可断开连接；多选后右键其中一个节点可一起复制或删除，复制会保留所选节点之间的内部连接。

顶部原有的工作流路径、保存、打开、离线节点、生成类型选择、添加生成节点、删除和重试入口，改由“工作流”菜单及画布上下文菜单承接；顶部保留工作流、运行、取消、继续运行及右键提示。右侧继续提供详细参数、源文件、历史预览和发布确认；节点保留“运行并预览”按钮作为直接入口。

支持鼠标右键、macOS 双指点按和 Control 单击。在画布中使用 Shift+F10 可打开上下文菜单，Command+D（其他平台 Ctrl+D）复制选中节点，Delete 删除。打开菜单不会执行生成；不可用项会说明原因。保存/打开工作流时通过对话框填写原有 JSON 文件路径，数据格式不变。

后台验证：设置 `AINATIVE_PYTHON` 后执行 `--headless --path samples/ainative-workbench --script context_menu_acceptance.gd`。该回归使用离线复制服务，验证实际编辑和预览，不调用模型。
