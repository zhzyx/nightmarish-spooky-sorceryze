# 马良撤除 GPT 独立网格生成

<!-- gonggong-request:maliang-remove-gpt-mesh-20261114 -->

2026-11-14，用户撤销了 [#543](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/543)，并要求删除 GPT 独立生成三维模型的逻辑。[#1079](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1079) 跟踪主线代码的撤除。

## 产品行为

- 删除由 Codex CLI 请求 GPT 原语建模计划和复杂建模计划的生产入口、设置及专属验证脚本。移除从旧节点、旧配置快照和直接 provider 调用发起的 GPT 建模。共用的 Godot、Blender 构造器供自选 API 模式继续使用。
- Codex CLI 继续生成二维图片。原先组合的「Codex CLI 图像 + 本机网格」模式由本机三维后端生成网格。离线复制、ComfyUI、混元三维、Kimi Native／Tripo 与其他受支持的 API 仍可使用。
- 自选 API 建模在配置时拒绝可识别的官方 OpenAI／Azure OpenAI 端点和明确的 GPT 型号。仅由私有转发服务解释的任意模型别名无法判断实际供应商。
- 旧工程配置改用 Codex 生图设置并保留 CLI 路径，重新配置网格后端需要用户操作。旧工作流继续保存原节点、参数和连线，已生成的资源可继续查看。运行仍指向旧 GPT 网格 provider 的节点会提示重新选择后端。

## 验收

- 通过旧设置、旧节点和旧运行快照验证迁移与拒绝行为，确保不会恢复、重试或转发 GPT 网格请求。
- 验证新的自选 API 建模配置拒绝官方端点及 GPT 型号，其他自选 API、CLI 生图和既有网格模式仍可进入各自的实际路由。
- 核对原工单的撤销状态。仅清理可确认属于原工单的本地样例、派生资产、临时资源和分支。
