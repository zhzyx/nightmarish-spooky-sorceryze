<!-- gonggong-request:per-ai-model-selection-20261112 -->

# AI 会话与马良节点独立选择模型

## 用户目标与授权

用户要求：任意 AI 模块（AI Chat、马良等）的任何一个会话、马良节点都能独立选择模型；设置里仅配置对应模型的登录或 API 地址。按 2026-11-12 当前会话明确指令实施。

## 范围与行为契约

- AI Chat 的连接方式、模型、手动模型 ID 和推理强度是当前会话的状态，选择器位于会话工作区。设置页仅保留 API 地址、密钥、CLI 登录和权限等接入配置，不再保存全局模型默认值。
- 新 AI Chat 会话可继承创建时的选择作为初始值，随后独立修改；已有历史会话继续恢复自己的后端与模型。
- 马良生成节点保存主模型 `model`；图像生成网格在需要重绘时另存 `image_model`。节点检查器与节点摘要显示该节点实际选择，工作流保存、打开和复制保留这些字段。
- ComfyUI 按每个节点的图像／网格模型创建或复用对应 Provider；Kimi 按节点选择模型；Codex 图像节点使用 `builtin` 或明确模型，指令建模／雕刻的 Mesh 节点可留空以明确使用 CLI 默认模型。服务方式仍由现有生成服务配置决定，不在本需求中新建多账号注册表。
- 旧工作流缺少节点模型字段时，从旧全局 `image_model`、`mesh_model`、`kimi_model` 迁移一次；旧运行记录仍按其原有 Provider 快照恢复。新运行的服务快照冻结节点模型，后续编辑不回写已在途运行。
- 设置中的模型检测只发现目录与能力，不选择或保存默认模型。凭据不进入会话历史、工作流或公开日志。

## 受影响模块与构建边界

- 原生编辑器：`editor/docks/ai_chat_dock.cpp` 及必要的原生回归。
- 马良内嵌工作台：`samples/ainative-workbench/addons/ainative/workbench.gd`。
- 马良嵌入 Python：`tools/ainative/generation_service.py`、`codex_provider.py`、`modeling_provider.py`、`sculpt_provider.py` 及测试。

这些文件均进入现有原生编辑器／内嵌资源构建输入。目标平台为 Windows x64 当前 Godot 编辑器；Python 单元测试不冒充真实模型推理验收。

## 验收与停止条件

1. 两个 AI Chat 会话可选择不同后端／模型，切换和重开后互不覆盖；设置页没有模型选择或默认模型保存入口。
2. 两个马良节点可选择不同模型，节点切换、复制、保存和重开保持各自选择；运行编译后的 Provider 与模型一致。
3. 旧会话和旧工作流无新字段时按旧全局值迁移；旧运行快照仍可恢复。
4. 设置检测不提交生成，不保存密钥；缺失或失效节点模型给出明确错误，不回退到其他节点或全局模型。
5. 受影响 Python 测试、GDScript／原生 AI Chat 回归和 Windows 编辑器构建按可用环境执行；真实付费模型生成不作为本地替身测试的完成证据。

暂不覆盖：统一多账号／多 API 端点注册表、旧高级自定义 Provider 的节点模型注入、真实供应商生成质量、非 Windows 平台实测。

## 2026-11-13 实际验证记录

- 使用 Windows 契约要求的真实 `pythonw.exe` 运行时执行 `tools/ainative` 的 8 个指定单元测试模块：共 137 项，132 项通过、5 项按原条件跳过。覆盖节点模型路由、Provider 复用与冻结快照、旧单数快照恢复、Comfy／Kimi／Codex／Modeling／Sculpt 服务，以及 `model_adjust` 按 Mesh 模型迁移。普通 `python.exe` 不满足 Kimi 工具运行时契约，不能作为该项通过依据。
- 使用最终 Windows 候选执行马良 GDScript 回归：Modeling 67 项、Sculpt 78 项、工作台统一设置 28 项、完整生成服务 GUI 104 项全部通过。覆盖新建、复制、保存重开、旧工作流迁移、逐节点模型、凭据排除及设置页无全局模型入口。
- 项目级 AI 配置的 full／reopen／other／child／scheduled 五阶段回归通过；原生统一设置的 full／reopen 回归均通过，严格脚本错误为空。覆盖接入控件唯一性、会话模型控件唯一性、目录授权、保存不写全局会话模型、跨作用域与重开恢复。
- 模型选择器原生回归通过 8 组检查：离线 Codex CLI 与 HTTP 夹具提供目录，推理强度、unsupported capability 禁用、无效路径重试、两种 HTTP 接口、CodeBuddy 默认能力，以及两个会话独立后端和模型均符合契约。该检查只枚举目录，不调用模型推理。
- 模型目录自动刷新回归的 16 个可执行场景全部通过，覆盖延迟状态结果在 UI 暂停后保留、目录只拉取一次、会话独立、登录竞态、HTTP／Responses、外部状态与配置变化等。`codebuddy-startup` 与 `backend-switch` 因本机没有可信 `job-object.node` 模块而未执行，不计为通过。
- HTTP 历史会话的 seed／restore／backup／corrupt 四阶段回归通过；两个会话分别恢复并向隔离 HTTP 夹具发送 `history-model-a`／`history-model-b`。HTTP `models` 目录取消、迟到响应拒绝与刷新恢复场景也通过，原生退出码为 0。
- 主线凭据绑定回归的 `openai`、`godot-unbound`、`godot-other`、`godot-bound`、`openai-official` 五种场景全部通过，确认保留最新 main 的凭据绑定和失效保护。
- 设计批处理的 7 个模型目录场景全部通过：`models-initial-ok`、`models-initial-fail`、`models-return-ok`、`models-return-fail`、`models-initial-stop`、`models-initial-cancel`、`models-no-live`。目录失败、停止或取消不会阻断既有业务请求与父任务返回。
- 最终 Windows MSVC 原生候选为 Godot `4.8.beta.custom_build.d5a77b1d5`，基线提交 `d5a77b1d539a9b92a1b81fc84c4df447dab82a7d`，SHA-256 为 `77a1299e55fcd99d1906e06a553a0f0c0e2f43138b8105dff62cc4a778b54aae`，大小 163343360 字节。采用标准编辑器配置 `platform=windows target=editor arch=x86_64 dev_build=no debug_symbols=no d3d12=no accesskit=no use_llvm=no -j16`，最终主线增量编译与主程序链接成功；上述最终原生报告均使用该候选或其 runner 私有副本，报告哈希交叉核验通过。
- 旧纯 `c074db21` 基线的 `dev_build=yes` 构建曾出现随机启动崩溃，普通并行和显式单工作线程下均为 5 次中 4 次失败；本次 `d5a77b1d` 标准配置需求候选连续 5 次隔离启动通过。根因仍未确认，本次不宣称已定位或修复开发优化配置的既有崩溃，也不把帮助生成、线程数、空图标或自更新写成根因。
- `test_owned_process` 与 `test_motion_provider` 合计 17 项，16 项通过、1 项按条件跳过。
- `test_kimi_direct_provider.py` 未计入本次通过范围：本机复跑仍有 URL 断言、PIL 缺失和临时文件锁问题，且未完成 main 基线对照；不能据此声称该模块通过或把这些问题归类为本次回归。
- 真实 Issue 为 [#971](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/971)，需求 ID 为 `per-ai-model-selection-20261112`，已通过开发准入。当前仍需完成正式门禁、提交、精确 PR head 的 CI、main 与 Issue 回读，不能把本地验证状态表述为正式交付。
- 未调用真实付费供应商生成；本地替身测试不证明真实模型质量、账号可用性或生成质量。非 Windows 平台未实测。
