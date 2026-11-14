<!-- gonggong-request:api-node-model-selection-20261114 -->

# 马良 API 节点独立选择模型修复

## 设计定版确认

用户已授权父 [#978](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/978) 的模型接入重构与范围内缺陷修复。本修订承接 [逐节点模型设计](per-ai-model-selection-20261112.md) 的马良验收 2、3、4，修复 API 建模／雕刻提前使用全局型号创建单 Provider 的缺口。不恢复已下线的 Codex 建模／雕刻，不扩大供应商、安全限制或模型执行权限。

## 生产工单

- [#1163](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1163)，需求 ID `api-node-model-selection-20261114`，责任者 Sail-Li。
- 验收: node-routing | API 建模与雕刻实际使用每个节点的明确型号；相同连接和型号复用 Provider，不同型号独立。
- 验收: migration | 只有缺少 `model` 字段的旧节点从旧 `api_model` 迁移一次；显式空、类型错误、非法／下线型号在节点入口给出可修复错误。
- 验收: frozen-restore | 新运行持久化每个 Provider 的连接及型号，设置和节点后续编辑不改旧运行；旧单 Provider 快照仍可恢复。
- 验收: connection-ui | 设置保留端点、凭据环境变量名和构造工具，移除全局型号选择；节点检查器、摘要、导入、复制及保存重开一致。
- 验收: verification-delivery | 两模式回归、原生 UI、独立审查、正式门禁、精确 CI、main 回读与任务资源清理全部完成后才可关闭本单；不据此关闭父 #978。

## 实现契约

`api_planner.validate_connection` 只校验连接；`validate_config` 在连接校验上追加实际请求型号及既有下线限制。检测只检查配置、指定环境变量存在性与本机构造工具，不查询外网或提交生成，也不依赖已经隐藏的旧默认型号。

`generation_service.prepare_provider` 先将缺字段旧节点迁移，再验证每个 API 节点的型号。按完整 Provider 配置复用实例，节点持久化相应 Provider 键；`providers`／`provider_types` 快照用于恢复，原有单数 `provider` 快照路径保留。节点不从其他节点或全局隐式回退。

新 API 节点初始 `model=""`，必须在检查器明确填写。工作台隐藏无目录支持的 API 型号下拉框与无效的辅助图像型号入口，摘要使用节点的实际选择。旧设置的 `api_model` 仅保留为尚未打开的旧工作流迁移来源；新设置不生成该字段，修改连接也不更新它，防止提前删除导致旧工作流失去迁移信息。迁移后的节点带有字段，保存后重新打开不会二次迁移。显式空字段始终保留并拒绝运行。

连接及凭据环境变量名保留在本机设置／运行服务快照，不进入可移植工作流；测试使用专用虚构环境变量，不读取用户凭据。

## 验证与证据边界

新增 `tools/ainative/test_api_node_models.py` 覆盖两模式的多节点、复用、非法值、一次迁移、连接检测、真实编辑器宿主创建运行、冻结恢复及旧快照。`samples/ainative-workbench/api_node_models_acceptance.gd` 在临时项目执行真实工作台控件与 Python 宿主检测，覆盖新建、检查器编辑、复制、摘要、保存重开、旧工作流导入和运行门禁。

本地运行使用已有且核对 SHA-256 的 macOS headless 二进制 `dcad14cd6457c992109ef6a1ad58303de167e96ecacca4ac487674f2c1ea90ea`，来源基线 `ca0badd8f82715dac6f6205f5f97e2086cac35b6`。这是当前 GDScript 的隔离原生执行证据，不是当前源码重建的安装包或 Windows 实测。已有本地 HTTP 夹具到真实 Godot 构造器回归与供应商协议回归分别保留结果；不证明真实付费供应商、账号或生成质量。

私有原始证据路径以主工作区仓库根为解析基准：`data-collection/receipts/ai-integration-refactor-20261112/api-node-model-repair/`。源码基线为 `6920cd30e9381105e27698cac918984ae7f2bb52`；实现初稿的摘要与验证记录在该目录的 `validation.json`。独立审查修正了非法类型经检查器转为字符串、非法带空格值被自动裁剪的两条路径；API 检查器保留原始输入，非法值必须明确修改。最终独立审查与精确六份实现/测试文件摘要见 `data-collection/api-node-model-selection-1163.json`，原始报告为 `api-node-model-independent-review/review-final.json`。最终 8 项专项、90 项正式原生及 112 项扩展原生检查通过（扩展包含正式检查，不重复计数）；独立审查不冒充 CI、main 或供应商验收。
