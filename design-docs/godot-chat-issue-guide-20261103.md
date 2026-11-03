# Godot 聊天未绑定工单时在会话内引导建单，不直接阻断会话

<!-- olympus-request:godot-chat-issue-guide-20261103 -->

- 需求 ID：`godot-chat-issue-guide-20261103`
- Issue：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/22（`work_items.py issue --apply` 创建；随后添加 `workspace:olympus`，状态设为 `status:in-progress`，经 `issue_gate.py --intake-only` 回读通过）
- 类别：`type:development`
- 责任人：待实际指定

## 原始需求与目标

用户原话：“在引擎里，如果 Missing host request: request_id，就在引擎内会话里引导创建新 issue，而不是阻塞会话。”

现状：`editor/docks/ai_chat_olympus.cpp` 的 `_begin_olympus_context` 把空的 `olympus/request_id` 原样交给桥接；`bridge.py` 的 `chat` 抛出 `Missing host request: request_id`（或 `issue_number` 无效时抛出 “Before development, create/reuse a real Issue…”），`_poll_olympus_context` 只追加一条错误并结束本轮。用户只能离开会话，到 Olympus 页手工填写，原始消息需要重新发送。

目标：未绑定工单时，会话保持可用，并在同一会话内一步步完成“复用已有 Issue”或“新建 Issue”。绑定校验通过后，用原始消息继续正常的 Olympus 入口。

## 范围与非目标

范围：

- 引擎聊天 dock：在调用桥接前检测本地绑定缺失（`request_id` 为空或不合规、`issue_number` < 1）；同时识别上述两类桥接错误。任一情况都进入“工单引导”状态，不按普通错误处理。
- 引导状态由宿主本地确定性处理，**不调用模型，也不执行工具**。这符合“未绑定则阻止模型及工具执行”的入口契约；引导并没有放宽这条契约。
- 引导分支：
  1. 复用：用户在会话中输入 `#编号 需求ID`，宿主写入 `olympus/issue_number`、`olympus/request_id`，再用原始消息重走正常入口校验。
  2. 新建：默认取本轮用户消息作为需求原文，在会话内依次确认类别（`.github/labels.json` 中唯一 `type:*`）、标题和建议需求 ID（`小写-连字符-日期`）。然后经桥接新动作在 `design-docs/` 生成需求文档（已存在则拒绝覆盖），并用 `work_items.py issue` 预览远程 Issue。用户确认后才执行 `--apply` 创建。
- 新建 Issue 时附加 `workspace:olympus` 标签，否则 `issue_gate.intake` 必然拒绝。
- 创建后状态仍为 `status:needs-decision`，是否开工由人工决定，引导不会自动修改。引导展示 Issue 链接和待办：用户在会话里明确回复 `开始`，才经桥接把待判断/计划中改为 `status:in-progress`（其他状态需到 GitHub 人工处理）；回复 `已更新` 表示已在 GitHub 改好，直接重试入口校验。
- 本机缺少 `gh` 或没有权限时，引导给出需求文档路径和可复制的创建命令，停在该步。不得声称已创建。
- 引导期间可随时取消；取消后会话回到普通状态，不残留半绑定的设置。

非目标：

- 不绕过、不放宽 `issue_gate` 的仓库、租户、标签、状态和需求 ID 校验。
- 未绑定前不写 Hermes 事件（没有可用的 `request_id`）。绑定通过后按现有流程记录。
- 不改共工共同框架、`Olympus/extensions/hermes-files/`、`olympus-hermes-data/` 的规则，也不替用户决定工单状态。
- 不扩大真实模型供应商验收范围。

## 设计方案

- `ai_chat_dock`：新增引导状态（`choose` / `category` / `title` / `request_id` / `drafting` / `confirm` / `creating` / `await_status` / `starting` / `retrying`），并保存触发引导的原始消息。引导状态下的用户输入由宿主解析，只写入界面记录，不进入 `messages` 发往模型。纯解析逻辑放在 `editor/docks/ai_chat_issue_guide.h`，便于原生单测。
- `bridge.py`：新增 `issue-draft`（生成需求文档并返回 `work_items.issue` 的预览计划）、`issue-create`（`--apply`，返回 URL 和编号，或 `gh_unavailable` 加创建命令）、`issue-start`（仅在用户明确回复开工时修改状态）。三个动作都是异步子进程，沿用现有轮询方式，不阻塞 UI。宿主环境会自动查找 gh。
- `work_items.py`：创建时的标签加入 `workspace:olympus`，状态标签保持 `status:needs-decision`。

## 依赖及风险

- 远程创建依赖 `gh` 登录及仓库写权限。编辑器从 GUI 启动时 PATH 里通常没有 `~/.local/bin`，桥接会按固定位置查找。
- 工作区里另有他人未提交的改动（`modules/camera/camera_apple.mm`、`samples/olympus-workbench/`、根目录构建记录），与本单无关，不暂存。
- 风险：需求文档由用户聊天原文生成，引导会提示用户先审查、脱敏，再创建远程 Issue。

## 验收标准

- [x] 未绑定时发送消息：不出现“Olympus 阻止本次发送：Missing host request…”的终止性错误，会话进入引导，且模型请求数为 0。
- [ ] 复用分支：输入有效 `#编号 需求ID` 后写入设置，并用原始消息重走入口。校验被拒时展示具体原因，并停留在引导中。（解析已有原生单测；绑定后重走入口的路径已在新建分支中实测；“直接复用”和“校验被拒后停留在引导”未单独做场景实测。）
- [x] 新建分支：生成 `design-docs/<需求ID>.md`（已存在则拒绝），给出预览；确认后通过模拟 `gh` 创建，带 `type:*`、`status:needs-decision`、`workspace:olympus`。
- [ ] 无 `gh` 时给出命令并停留，不报创建成功。（桥接返回 `gh_unavailable` 加命令已有单测；编辑器内的提示文案未做场景实测。）
- [ ] 引导中取消、会话切换、迟到的子进程结果都不会恢复旧请求，也不会写入设置。（取消已做场景实测：零模型请求、零 GitHub 调用、零事件；会话切换和迟到结果靠代次计数保护，未做场景实测。）
- [ ] 桥接单测覆盖新动作；原生 AIChat 测试覆盖引导状态机；受影响的现有测试通过。（桥接 9 项新单测；原生测试覆盖纯解析逻辑，状态机由编辑器场景覆盖；`run_olympus_chat_gate.py` 中 Issue #6 之前的旧模式本次未运行，见下文。）

## 执行范围与验证

产物：引擎聊天 dock 源码、`bridge.py`、`work_items.py` 及对应测试。平台：当前 macOS 开发机，编译受影响的编辑器目标。最小验证：`customizations/components/godot-host` 和 `issue-workorders` 的 Python 单测、原生 AIChat 测试。不默认扩展到其他平台或发布包。

## 验证与采集证据

2026-11-03，在本机 macOS 13.7.8 x86_64、Apple Clang 14（`allow_unsupported_apple_clang=yes`，属实验性构建，不是受支持的工具链）上完成。证据源：[data-collection/godot-chat-issue-guide-20261103.json](../data-collection/godot-chat-issue-guide-20261103.json)。

- 增量构建 `scons platform=macos target=editor use_volk=yes accesskit=no allow_unsupported_apple_clang=yes [tests=yes] -j4` 成功：不含测试 2 分 37 秒，带测试 1 分 16 秒。
- 原生测试 `--test --test-case="*AIChat*"`：17 项、194 条断言全部通过，含新增 2 项。
- Python：`godot-host` 27 项（新增 9 项）、`issue-workorders` 39 项，在 `TMPDIR=/private/tmp` 下全部通过。默认 macOS 临时目录下，HEAD 本身就有 8 项失败（`/var` 与 `/private/var` 的符号链接问题），与本单无关、未修改，本次改动前后结果一致。
- 编辑器场景 `tests/editor/run_olympus_chat_gate.py`：
  - `--mode issue_guide` 通过。流程为：未绑定发送 → 引导 → `新建` → 类别 → 默认标题 → 需求 ID → 需求文档预览 → `确认` 创建 #42 → `开始` → 原消息完成一轮模型回复。全程 1 次模型请求，引导回复未进入模型消息，8 条 Hermes 事件均属该需求 ID、来源为 Issue URL，UI 最大帧间隔 0.053 秒。
  - `--mode issue_guide_cancel` 通过：零模型请求、零 GitHub 调用、零事件，未生成需求文档。
  - 两个场景都用隔离的 `HOME`、模拟 `gh` 和模拟上下文输出（本机没有 node），没有触达真实仓库或真实框架准入。
- 未覆盖：`run_olympus_chat_gate.py` 的其余模式仍断言 Issue #6 之前的事件来源 `godot-editor:chat-context-loader`，且未绑定工单，本次未运行也未修复；Windows 及其他平台未构建；真实 GitHub 上的引导创建未在编辑器内执行（Issue #22 本身由命令行 `work_items.py issue --apply` 创建）。
- 用量：token、费用均未计量，记为 null。
