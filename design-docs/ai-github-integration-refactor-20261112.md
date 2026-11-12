# AI 与 GitHub 接入复盘及重构

<!-- gonggong-request:ai-github-integration-refactor-20261112 -->

父 Issue #978。用户要求遍历当前工程所有 AI、GitHub CLI/API 内容、需求、BUG 和阻塞，复盘后完整重构模型选择与接入，清理重复入口、保持清晰可恢复的交互。2026-11-13 仍在执行，以下为已核实边界与未完成范围，不能作为整体验收完成回执。路径以仓库根为基准。

## 来源与已有交付

本次主线起点为 `08fe645a2296f8145185c9ea087fd4ab3ac345ed`。前置 #973 已经 review 原52个工作树，保留有独有改动、运行引用和未结束任务的33个，清理19个，PR #977 合入。完整原因和逐树结果见 `workspace-review-cleanup-20261112.md`。

本次私有源索引已发现362个相关源码/配置文件；工单快照472条中按标题检索到273条AI/GitHub相关项。数字仅描述初始候选检索，不声称逐个业务验收。旧工作树、archive和历史批准只作为追溯，不重新启用旧候选。

## 当前职责与重复来源

| 层 | 当前来源／消费者 | 本次处理方向 |
|---|---|---|
| 原生聊天 | `editor/docks/ai_chat_dock.cpp/.h`：设置、会话、目录、验证、推理和子工作者 | 连接快照与模型选择分离，降低控件和异步任务耦合 |
| 凭据记忆 | `editor/docks/daqian/session_memory.gd`：项目/backend/endpoint绑定、epoch保护 | 补齐环境凭据来源与实际目标绑定，保留已有迟到回调保护 |
| 个人模型库 | `customizations/components/godot-host/daqian/model_catalog.py`、`model_api.py`、`local_models.py` | 明确选择不回退；凭据版本绑定live回执；目录发现不等于推理可用 |
| 天枢入口 | `editor/docks/daqian/model_settings.gd`、`workspace.gd` | 停止跨层遍历控件重构配置，采用稳定访问方法；个人库刷新与原生目录刷新分别留证 |
| 马良 | `samples/ainative-workbench/addons/ainative/workbench.gd`、`tools/ainative/generation_service.py`及Provider | 接收#971逐节点选择与冻结运行快照，再接入共享连接边界 |
| 宿主运行路径 | `tools/gonggong_runtime_config.py`、原生`GongGongRuntimeConfig`、`environment_igniter`、CLI发现 | 核对来源优先级、路径更换、安装来源与当前进程快照；移除无必要的重复发现 |
| GitHub访问 | `daqian/repository_access.py`、`issue-workorders/work_items.py`及bridge的`find_gh` | 统一可执行发现与错误边界；认证身份、权限和网络失败分别呈现 |
| API协议 | `customizations/platforms/ai-access/daqian/http_protocols.py` | 复用已有协议契约，不按模型名推测能力 |

## 已确认问题与承接

- #979：显式Codex验证失败后继续调用CodeBuddy；凭据替换沿用live证明。修复增加范围隔离、pending/ready凭据版本及写回比较。独立review的两处并发补充已修复，20项合成回归通过；交付回读单独记录。
- #980：项目自定义端点与环境密钥可能错配，且已有非空key会跳过绑定凭据恢复。独立隔离工作树正在修复原生列表、验证、推理、子工作者和记忆恢复；用合成密钥loopback证明，不向未知地址发送真实密钥。
- 目录身份比实际会话签名弱：CLI路径未覆盖CODEX_HOME、账号代次、环境及安装来源。需要复现同路径切换期间迟到目录结果与旧能力准入。
- 目录失败或取消后，同配置事件已消费而无明确retry入口；CodeBuddy登录完成未连接目录刷新。修复必须区分避免自动循环和允许用户明确重试。
- `models_loading`同时锁住发送、设置、会话创建和切换。应分离目录任务与会话执行，保留已有手动模型的可操作性。
- 老`model_picker.gd`把backend当refresh按钮发pressed，未覆盖当前item_selected刷新契约；修复回归等待真实fixture请求/状态变化。

## 与其他在途工作协调

#971由另一操作者负责AI Chat每会话及马良每节点的独立模型选择，当前主线未包含其候选。其已回读内容包括129项Python（5跳过）和马良脚本测试，但Windows完整候选因磁盘/宿主条件未完成；这不是本任务的完成证据。继续保持其所有权和工作副本，接收交付后整合，不覆盖其实现。#978负责连接、凭据、目录及跨入口访问契约。

相关开放验收包括#840提供方独立性、#843非Codex宿主、#706真实服务与延迟、#593HTTP流、#217模型/强度、#522网络等待、#954再次发生的启动环境/目录问题。已关闭#750路径审计、#828项目配置、#857启动同步、#867记忆作为回归来源；关闭状态不证明新发现问题已解决。

## 共享契约

连接记录包含稳定ID、provider/protocol、规范端点或运行配置引用、凭据句柄及目标范围；明文密钥不进入目录、会话、工作流或公开日志。每次操作冻结连接版本、认证代次及运行环境来源。

会话／节点模型选择由#971负责，以连接引用、准确模型ID或明确默认模式、推理强度为字段；新建只继承一次，运行冻结快照。目录按连接快照保存模型及明确能力、来源和状态；失败、取消、过期不能伪装为可用。验证回执区分发现、认证、文本、图像和网格，绑定实际连接版本。

稳定方法承接`get_connection_snapshot`、`resolve_credential_for_endpoint`、`get_model_catalog`、`refresh_catalog`、`cancel`、`get_effective_selection`。保留必要迁移适配，逐步停止GDScript依赖控件名字和父节点；这些方法名是设计方向，尚未全部实现。

## 整体验收

1. 入口、当前需求、缺陷、阻塞及责任/溯源有可核对映射。
2. 登录／地址／凭据归连接，会话／节点归模型选择；无重复默认模型设置。
3. 不静默更换提供方或模型；发现、验证和实际能力分别标识。
4. 认证、离线、超时、取消、重试、迟到回调、重启恢复均有可执行回归。
5. GitHub CLI/API和模型宿主路径一致可诊断，权限和未知发布回执按原边界处理。
6. 必要单元、原生headless、已有可用账号代表实测完成；缺失平台/账号证据明确保留unknown。
7. 独立review、正式门禁、精确CI及远端main回读完成，整体验收关联Issue按实情关闭。
8. 清理本任务废弃资源，保留其他工作者、有效安装及必要回退证据。

当前尚未满足上述整体验收；子项交付不会提前关闭#978。
