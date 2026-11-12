# AINative 交换契约 v1

本目录从 01-contracts 的可执行交换契约起步，现已包含持久 Executor、Godot Workbench、真实 ComfyUI／Codex／Kimi Native Provider，以及预览、审核发布和下游资产入口。核心 Python 代码使用 Python 3.11+ 标准库；真实生成与构造仍需各自配置的外部服务或可执行文件。所有相对路径以仓库根为基准。

运行：

```text
python tools/ainative/contracts.py tools/ainative/example.json
python -m unittest discover -s tools/ainative -p "test_*.py"
```

Artifact 必须含 id、revision、type 和 payload 对象。dependencies 和 context.artifact 使用 {id, revision}；当前交换包必须闭合引用。扩展 type/payload 无损保留，领域插件负责额外校验。revision 是调用方提供的不可变版本标识，内容寻址与存储强制不可变由 02 实现。

context 条目必须有 role、scope、strength（reference/constraint），以及 text 或 artifact 二选一。scope 当前为插件解释的字符串；内核不静默展平上下文。

binding.level 包含 unbound / semantic_mapped / animation_retargeted / target_bound / roundtrip_verified。后四者要求 skeleton_profile 引用；已绑定 garment 另需 character/avatar_profile 作为 fit_target；回读声明需 validation_report 引用。校验器检查声明结构，不能证明几何拟合、蒙皮、目标工具回读确实成功；实际证据内容校验属于各领域验收。

验证报告的 payload.subject 必须为被验证资产的 {id, revision}。binding.evidence 是非生产引用，不加入生产 DAG，因此报告可以通过 dependencies 记录其验证对象而不会形成伪循环。

example.json 全部是合成契约夹具，UE/Mixamo Profile 是占位元数据，没有真实骨架/网格，不可作为兼容实现或真实生成样例。

`extensions.py` 提供可执行的扩展契约：

- `NodeRegistry.register/get`：注册可 JSON 序列化的版本化节点定义；输入、输出端口分别声明 types 和 required；同 id/version 的定义不可替换，读写边界深拷贝。类型名称不设全局白名单，领域扩展可自行声明。
- `validate_invocation(registry, request, manifest, provider)`：检查必需端口、版本引用、类型、参数与上下文能力，返回 SHA-256 调用键。节点定义、完整输入包、Provider/模型版本、参数、带 role/scope/strength 的上下文都参与计算；当前保守包含整个包，因此无关资产变化也可能失效。存储层仍需保证版本不可变。
- 参数 schema 使用明确子集：顶层 properties/required，属性支持 type/enum；type 支持 string/integer/number/boolean/object/array。未知参数和未知 schema 关键词拒绝，object/array 内部仅保证 JSON 值，不宣称完整 JSON Schema。参数不自动填默认值。
- `provider_manifest` 验证 Provider 和模型的固定版本、能力、上下文类型、可用性；`Provider` Protocol 定义 describe/submit/poll/cancel。submit 必须接收 idempotency_key；是否真正保证幂等由具体 Provider 与 #143 执行器验证。凭据不属于序列化定义。
- `validate_job` 检查任务身份、状态转移及终态不可变；queued 可直接观测为 succeeded。只有 succeeded 可带非空 outputs；failed 必须有 error。`validate_outputs` 进一步对照节点端口和输出资产清单验证结果，执行器应在发布前调用两者。
- `PublishAdapter.encode` 是受信任纯编码接口，输入为深拷贝，输出 bytes。`publish_new` 将单文件写入同目录临时文件并以独占硬链接原子发布；目标存在时拒绝，编码/链接失败不会覆盖源文件，临时文件清理。调用方提供存在且受信任的目标目录；不支持硬链接的文件系统报错，不降级为覆盖写入。多文件事务、Godot Resource/Scene 编码及实际发布适配器由 #144 提供。

扩展调用顺序：注册定义 → Provider.describe → validate_invocation → submit/poll/cancel → validate_job/validate_outputs → publish_new。该顺序是 #143 执行器的接口，不代表当前已实现调度、重试或真实生成服务。

单元测试的 Provider 元数据、编码器和 UE/Mixamo 目标请求均为显式合成夹具。#142 的交付是契约及其可执行验证；ArtifactStore、任务持久化和引擎 UI 仍属于后续工单。

## Real ComfyUI provider (#145)

`comfy_provider:factory` registers `text_to_image`, `image_to_image`,
`image_to_mesh`, `text_to_mesh`, plus the existing `local-copy` demo. The editor's
`+ Generate` selector creates the four typed nodes. Text nodes have no source port;
image nodes require an image, and mesh outputs cannot feed image inputs.

Copy `comfy-config.example.json` **outside the repository**. Replace the two
checkpoint SHA256 values with hashes of the installed files, and record the exact
ComfyUI commit in `backend_revision`. Checkpoints belong to the backend's
`models/checkpoints`; `name` is a basename, not a path. `storage` resolves relative
to the config file. It contains durable SQLite provider receipts/results and must
survive host restarts. Start the installed backend separately, for example:

```powershell
& $ComfyPython "$ComfyRoot/main.py" --listen 127.0.0.1 --port 8188 --lowvram
$env:AINATIVE_COMFY_CONFIG = 'D:/local-config/ainative-comfy.json'
& $Python tools/ainative/generate.py --db D:/local-state/art.sqlite --kind text_to_image --prompt 'a small stone owl sculpture, white background' --seed 11 --output D:/local-state/image-package.json
& $Python tools/ainative/generate.py --db D:/local-state/art.sqlite --kind image_to_image --source D:/inputs/owl.png --prompt 'red stone owl sculpture' --seed 12 --output D:/local-state/edit-package.json
& $Python tools/ainative/generate.py --db D:/local-state/art.sqlite --kind image_to_mesh --source D:/inputs/owl.png --output D:/local-state/mesh-package.json
& $Python tools/ainative/generate.py --db D:/local-state/art.sqlite --kind text_to_mesh --prompt 'a small stone owl sculpture, white background' --seed 13 --output D:/local-state/text-mesh-package.json
```

The CLI prints the durable run ID before polling; use `--run ID` with the same
`--db`, config and a fresh output filename to resume. It never starts inference
services. Editor local settings use this Python interpreter and factory
`comfy_provider:factory`; start Godot from an environment with
`AINATIVE_COMFY_CONFIG` set. Preview decodes PNG/GLB and existing review/publish
creates new `.tres` / `.tscn` files. Graph saves embed input snapshots and omit
endpoint, storage, factory, credentials and input filesystem paths.

The image path uses SD-Turbo's checkpoint, text conditioning, Euler sampling at
CFG 1, then VAE decode. A single image context becomes the img2img initial latent.
`image_to_mesh` without text uses Hunyuan3D vision conditioning directly; appended
text explicitly causes SD-Turbo img2img **before** Hunyuan3D. `text_to_mesh`
composes image synthesis and Hunyuan3D in one prompt. Hunyuan3D does not consume
text directly. Mesh extraction uses `VoxelToMesh` with `surface net`, followed by
`MeshSmoothNormals` at a 180-degree crease angle before `SaveGLB`. This emits
vertex normals for lighting in Godot; it does not add texture, rigging or topology
repair. Current mesh output is untextured geometry, not a rigged avatar.
Source plus another image, multiple image contexts, unsupported role/scope or
input types fail explicitly; no context is silently dropped. A reference image
can be supplied to text nodes with `--image-context` or the inspector. This is
single-image img2img conditioning, not guaranteed identity/style preservation.

Parameters: `prompt`, `seed`, `width`/`height` (64–1024 in multiples of 8),
`steps` (1–8, default 1), `denoise` (strictly between 0 and 1, default .65),
`mesh_steps` (1–50, default 20), `mesh_resolution` (1–4096, default 512 for Hunyuan3D-2mini),
`octree_resolution` (16–256, default 128). Seed defaults to 0 in the provider.
All effective defaults, prompt/context usage, source manifest digest, model
hashes, backend revision, provider source/config fingerprint and workflow hash
are stored with the output bytes and SHA256. Configuration/model declarations
must match installed backend files; this HTTP API cannot remotely attest model
bytes. Changing them invalidates Executor caches.

SQLite claims a key before POST. After a lost receipt, only `/queue` and
`/history` are searched for the exact key and graph. Missing/evicted history
remains unknown and never triggers automatic resubmission. This guarantee is
local to shared provider storage; ComfyUI itself is **not globally idempotent**.
Keep Executor and provider stores together. HTTP 400 rejects a prompt definitively;
connection loss/5xx remain ambiguous. Returned history must match the owned graph,
key and remote ID. Only that prompt's `output` node and same-origin `/view` may
supply a file, with a strict generated filename/subfolder and no redirects.
Cancellation deletes only an owned pending queue item. Running jobs are locally
cancelled and their eventual output discarded; `/interrupt` is never used because
it can interrupt other clients. Terminal local receipts cannot be overwritten by
late workers. Backend HTTP calls occur only in subprocess workers.

Validation: `python -m unittest discover -s tools/ainative` includes the original
39 tests and localhost HTTP fault tests. These validate protocol handling, not
model quality or real inference. Run the four commands above against actual
weights for generation acceptance; keep their packages and Godot preview/publish
receipts. No real inference claim follows from the HTTP fixture suite.

For the installed runtime layout (`ComfyUI-src`, `venv/Scripts/python.exe`,
`models/checkpoints`, `config.json`), one PowerShell entry sets process-local
configuration, starts ComfyUI only when its health endpoint is unavailable, checks
required nodes and opens Godot:

```powershell
./tools/ainative/start_local.ps1 -RuntimeRoot D:/local/ainative-local -GodotExe D:/Godot/godot.exe
```

`-Config` overrides the config location; `-Project` selects the workbench project;
`-BackendOnly` omits Godot. It never installs or downloads dependencies, changes
global environment variables or interrupts an existing backend. Runtime logs are
`comfy.stdout.log` / `comfy.stderr.log`. The launcher supplies Python and `comfy_provider:factory` through process-local
environment values; the workbench reads these on launch. The trusted config is
inherited by the launched Godot process. Native-only startup disables custom/API
nodes and browser auto-launch, with low-VRAM offloading and a 1.5 GB VRAM reserve.
Replacing model files requires updating their declared SHA256 in the local config;
the provider does not automatically inspect or attest remote model contents.


The Godot editor transports JSON numbers as doubles. At editor `create`, the host
uses the registered node schema to normalize only `integer` parameters: finite,
whole-number values within ±9,007,199,254,740,991 become Python integers. Fractions,
booleans and values outside that safe range are rejected; `number` fields retain
their original type. For the generation nodes, edit `seed` in the range
**0–9,007,199,254,740,991** in Godot. Direct Python/CLI integer inputs keep their
existing contract and provider range; core validation remains strictly typed.

## Real Kimi Native Mesh provider (#646)

`kimi_native` adds text-to-Mesh and image-to-Mesh without replacing any existing
provider. `generate.py --provider` still defaults to `comfy`. The Workbench exposes
Kimi Native as a separate generation-service choice; choosing it does not require
ComfyUI, Hunyuan3D, ChatGPT/Codex or Blender configuration.

The Native route is deliberately two-stage and is recorded as such:

1. Kimi receives the modeling instructions and optional source image and returns one
   strict JSON-Schema primitive plan. Model output is data, never executable code.
2. The existing fixed `modeling_builder.gd` constructs Godot box, sphere, cylinder,
   capsule and torus primitives and exports a self-contained GLB. The host independently
   checks embedded GLB structure, indices, nondegenerate triangles, finite coordinates,
   TRS/world bounds, vertex/triangle/byte budgets and the native builder receipt before
   publishing the artifact. It never substitutes an old GLB or another provider's result.

The closed plan allows 1–64 named parts; plan bytes, output bytes (64 MiB), vertices,
triangles and numeric ranges are bounded. This is basic primitive geometry with opaque
materials, not direct per-vertex neural generation, texture synthesis, production
retopology, automatic humanoid rigging or animation. Sampling, seed and mesh-extraction
parameters do not affect Kimi Native and are recorded as `not_applied` when supplied by
a generic CLI. Only `text_to_mesh` and `image_to_mesh` are accepted; 2D image nodes,
multiple images and unsupported context semantics fail explicitly. One PNG or JPEG
source can be combined with node-level text constraints.

### Local configuration and credentials

Copy `kimi-config.example.json` outside the repository and replace `Godot.exe` with the
actual local Godot executable. Keep `builder_path` pointed at the trusted built-in
`modeling_builder.gd`. The configuration has exactly five fields:
`endpoint`, `model`, `storage`, `godot_path`, `builder_path`. Relative `storage` resolves
beside the configuration file and contains the durable `kimi-native-jobs.sqlite` plus
private per-intent receipts. Use a durable location outside the repository.

Set `AINATIVE_KIMI_CONFIG` to that file for CLI/factory use. Set either `KIMI_API_KEY` or
`MOONSHOT_API_KEY` in the local user/process environment before launching the CLI or
Godot. Never put a key in JSON, node parameters, command-line arguments, workflow files,
logs or evidence. Only the key-owning `--probe` / `--api` Python children read it; the
parent, persisted configuration, GLB and provenance do not receive it. Connection checks
use `GET /models` and do not generate content.

The default endpoint is `https://api.kimi.com/coding/v1` and the default model is
`k3.1-pro`. Only official HTTPS endpoints and an explicit K3/K3.1 model allowlist are
accepted; discovery does not silently choose another model. Redirects, ambient proxies,
credential-bearing URLs and arbitrary relay endpoints are rejected.

### CLI, recovery and provenance

From the repository root, with the local environment and config already set:

```powershell
& $Python tools/ainative/generate.py --provider kimi_native --kind text_to_mesh --prompt 'a small four leg wooden table' --db D:/local-state/art.sqlite --output D:/local-state/text-kimi-package.json
& $Python tools/ainative/generate.py --provider kimi_native --kind image_to_mesh --source D:/inputs/reference.png --prompt 'match the pictured object structure' --db D:/local-state/art.sqlite --output D:/local-state/image-kimi-package.json
# Resume/read the same durable run; use a fresh output filename:
& $Python tools/ainative/generate.py --provider kimi_native --run RUN_ID --db D:/local-state/art.sqlite --output D:/local-state/resumed-package.json
```

The CLI prints the run ID before polling and does not start inference services. Each new
durable modeling intent performs at most one Chat Completions POST. Network loss,
timeout, an unknown worker exit or an unknown response never causes an automatic second
POST. Resume with the same run, database and local config; this reads the existing intent
and terminal result rather than creating a new generation. A deliberate retry is a new,
explicit user action. Cancellation terminates only processes owned by that intent; it
does not interrupt shared services or other jobs. Late output cannot overwrite terminal
state.

Raw prompts, source images, API responses and builder diagnostics remain in private
storage. Artifact provenance records the model and response ID, request/response/plan/
GLB hashes, allowed token usage, source hash, builder hash and geometry, plus the two
stages `kimi_strict_modeling_plan` and `fixed_godot_primitive_construction`. It also
records `fallback_used=false` and `generated_code_executed=false`. Public summaries must
omit raw prompts, base64, API keys, full responses and machine-private paths.

For tests, run `python -m unittest discover -s tools/ainative -p "test_*.py"`; HTTP tests
use local fixtures and do not prove real inference. Real generation acceptance requires
both commands above, the private receipts, independent GLB validation, and Godot preview/
staging/confirmed-publication/process-independent reopen checks. Fit must actually read
the resulting mesh; a result such as `needs_landmarks` is not an automatic rigging
success. Keep real rendered screenshots separate from headless geometry receipts. A
loadable GLB and a nonblank screenshot do not by themselves establish production visual,
topology, material, rigging, animation or performance quality.

## Kimi Work text-to-image and image-to-image (#808)

The `kimi_native` Workbench service mode is a composite route. Mesh nodes keep using
`kimi_native` and its strict K3.1 Pro planning/Godot-construction boundary. The
`text_to_image` and `image_to_image` nodes instead use `kimi_work_image`, an independent
Kimi Work `agent-gw generate_image` v2 service. K3.1 Pro does not directly generate these
2D images, and this integration neither replaces nor disguises ComfyUI or Codex.

In AI settings, select the installed plugin's `scripts/image_generation_tool.py` and the
windowless `pythonw.exe` returned by the official `resolve_image_powershell.sh` resolver.
The two local paths can also provide initial values through `KIMI_WORK_IMAGE_TOOL` and
`KIMI_WORK_IMAGE_PYTHONW`; saved machine settings take precedence when reopening. They
stay in private local configuration and run-scoped SQLite snapshots, never workflow JSON.
Kimi Work SDK authentication remains with the SDK. No credential is read by discovery,
stored in node data, printed in public logs or committed as evidence.

Discovery checks only the local scripts and runtime. It does not upload, generate or claim
that credentials/quota/network are valid. Mesh and image capabilities are reported
independently, so an absent image tool does not disable a working Mesh route. Actual
2D requests default to 1024×1024; both dimensions must be multiples of 16, at most 3840,
with 655,360–8,294,400 pixels and aspect ratio no greater than 3:1. Seed, sampling steps
and denoise are not applied and are hidden for these nodes.

An image edit accepts one PNG/JPEG source or reference. On an actual run, the official
`image-to-url` command uploads it before generation; this is not part of discovery.
Launcher and watcher use the configured windowless interpreter, with an intent persisted
before upload or generation. A timeout, network error or unknown receipt is never
silently retried. Cancelling fixes the local terminal state but cannot promise to revoke
a remote request. Restore continues the existing durable record rather than replaying it.

Only a new output file from that intent is accepted, after complete PNG/JPEG decoding,
dimension and SHA-256 validation. Image edits cannot return the unchanged input bytes.
Provenance identifies `kimi_work_image`, generation v2, input/output hashes, dimensions,
tool fingerprint and controls not applied; reference URLs and raw logs remain private.
Tests use synthetic local tools. They do not establish real image quality or prove a real
generation; native-editor acceptance must retain the real run IDs, artifact files,
provenance summaries and rendered Workbench screenshots separately.
