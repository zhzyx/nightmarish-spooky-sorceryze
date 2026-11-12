# 资产生成的后端独立与公共基础解耦

父需求：provider-independence-20261112。用户于 2026-11-12 明确要求执行并修复全部已审计 Codex 强依赖，授权当前会话持续交付。

范围：马良本机图生网格独立模式；Godot/Blender 语义规划接入明确配置的非 Codex API；将通用任务及图像/进程辅助从 Codex Provider 提取，Kimi 不导入 Codex 专属模块；保留既有配置、快照、取消和不可变结果。无 CLI 环境的代表成功与失败回归；网络用本机协议服务，不冒充真实生成质量。保留 Codex 专用模式，不默认选择它；Comfy 承担已有非 Codex 二维路线，不抢占 #808 Kimi Work 图像。写入责任 tools/ainative、samples/ainative-workbench/addons/ainative 和本设计。嵌入代码需原生构建消费核验。Windows x64 主验收，跨平台未知保留。主线接收与完整验收后关闭。

实现与本机验证（2026-11-12，#842）：

- `local_mesh` 为独立直接图生网格模式，内置包首次选择此模式；`LocalMeshProvider` 限制节点和重绘提示，仍使用原 Comfy 请求、恢复、取消和不可变结果契约。旧 `codex` 配置不迁移。
- `api_modeling` / `api_sculpt` 由用户明确配置 endpoint、api_model、api_key_env；仅支持 Chat Completions 的严格 JSON Schema 协议。API 返回数据走既有 Godot/Blender 计划验证及固定构造器。保留 Blender 校准图、输入图像语义、隐藏面声明等验证。
- `provider_common.py` 承担持久任务、图像验证和普通进程环境；Kimi 无直接或传递 Codex 模块导入。旧 Codex 图像验证导出保留。CLI 环境清理仍用于显式 CLI 子进程。
- 新 `api_planner.py` 由任务拥有的 Python 子进程执行单次请求；拒绝重定向，无自动重试/CLI回退，凭据只从环境读取。持久配置保存变量名，不保存值。快照保留完整端点/模型配置，回执区分 requested_model 和实际 observed_model。检测只检查本机配置，不冒称远端可用。
- API 支持 HTTPS 和 loopback HTTP（后者用于本机服务与协议 fixture）；不能保证任意第三方兼容严格 JSON Schema 或多图输入。不支持的服务显式失败。

验证命令（从项目根）：

```powershell
py -X utf8 -m unittest discover -s tools/ainative -p test_provider_independence.py -v
$env:AINATIVE_TEST_GODOT = '<本候选Godot绝对路径>'
$env:AINATIVE_GUI_TEST_GODOT = $env:AINATIVE_TEST_GODOT
py -X utf8 -m unittest discover -s tools/ainative -p test_provider_independence.py -v
```

首轮新增7项测试6通过、真实Godot项因本机路径不可用跳过；其后新增UI模式保存恢复项，等待父会话候选编辑器验证。协议成功/非法计划拒绝/取消不请求/快照恢复/无Codex模块及PATH/Blender校准与语义约束已验证。旧Codex/sculpt/Kimi/service/GUI回归90项通过，5项环境依赖跳过。全部在线模型结果为本机HTTP fixture；没有声称真实供应商推理质量或额度验收。

构建消费者按已验证 trace-native-consumer 方法召回：两个新Python模块与修改的Python/GDScript均为原生嵌入输入，由父会话追踪SCsub和本候选编译，不按文件后缀声称热更新。当前没有包热替换方案；回退需回退原生候选。输入为配置、结构化图/上下文、图像和模型JSON；宿主接口为现有generation_service与固定builder；回退保留旧模式/快照并拒绝自动切换供应商。Windows候选编译/真实Godot结果由父会话补充；实际Blender构造和跨平台未知保留。

最新验收分工：用户于本次任务中明确“暂时不用验收非 Codex，其他人会验证 Kimi 能力”。因此当前会话不等待真实第三方 API 配置或真实 Kimi 生成质量验收；交付核对保留本地协议、真实固定构造器、旧 Codex 兼容、构建与来源准确性。真实非 Codex 模型效果由后续责任者验证，不能将本机 fixture 或构造器成功表述成真实供应商质量已验证。父会话已报告使用既有只读 Godot 二进制运行新增测试 8/8 通过，含 API fixture→真实 Godot 与 UI 模式保存恢复；最终候选仍应复验。新增单图 API 来源测试明确 sheet_view_evidence.source=api_observed_panels、validated_api_modeling_instructions，且无伪造 CLI thread/usage。

独立审查修订：UI新增模式保存前校验地址、凭据环境变量名、模型ID及本机端口；拒绝含用户密码/query、非法端口、空模型和非本机网格地址，保留已保存配置原始字节。Codex指纹补入provider_common实现摘要，公共行为改变使旧指纹失效。已用 `D:/GongGong/.worktrees/issue-progress/bin/godot.windows.editor.x86_64.console.exe` 只读既有二进制预验新增10项全部通过（13.208秒）；该路径不代表本次最终候选，最终候选构建/复验由父会话负责。Ruff check/format和范围内diff-check通过。

## 主线交付与结束回执

PR #872 已合入 main `e15a49f9b7dbbdbb1b585fc2b68cc3f252d88c8b`。最终实际编辑器 SHA-256 `871e830723fb3d3c946fbdf44af2bfb1443d524a41d35f9c501050e34b45315f` 的10项独立性回归全部通过，含 API fixture 到真实 Godot 构造、设置保存及重开；最终源码与输出对绑定见 `data-collection/provider-independence-840-2d0-binding.json`。既有146项回归通过，3项依赖真实 Blender 的扩大几何覆盖未执行，不计通过，也不以非 Codex 推理免验替代。

用户配置的真实 Codex CLI 已生成五部件有效 GLB，重建 Provider 后恢复 succeeded；产物及 CLI 证据见 `data-collection/provider-independence-840-live.json`。原责任者独立复核代表验证契约已满足，#842 已以 completed 关闭并回读 status:done。Kimi及第三方真实推理质量按用户分工由其他责任者验证；父 #840 的 macOS 桌面宿主链路仍由 #843 保留。
