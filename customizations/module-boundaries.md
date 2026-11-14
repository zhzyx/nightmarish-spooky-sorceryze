# 接入子模块边界与现有实现映射

本文件定义接入职责结构，关联 Issue #111（需求 module-boundaries-20261105）。路径统一以仓库根解析；链接相对本文件。依据 [模块规范](../framework/specs/module-system.md)，只定义职责、现有归属和后续接入方式，不改变运行入口、注册状态或既有批准。下列 ID 是逻辑命名，不是已注册可执行模块；customizations/platforms/components.json 仍记录当前组件现状，customizations/module-migration.json 保持历史证据。

现行目录见[按平台选择接入子模块](platforms/README.md)。以下表格保留各职责的细分说明。

## 当前 Git 相关职责细分

Git 提供版本控制，GitHub 提供 Issue、子 Issue、PR 与服务权限；二者分别声明依赖。“Git 接入”是组合名称，不能作为所有子能力的不可拆前提。

| 逻辑子模块 | 职责与输出 | 当前实现／配置归属 | 边界与现状 |
| --- | --- | --- | --- |
| git-markdown-documents | 将偃师结构化需求／设计保存为仓库内 Markdown，返回文档引用、内容版本与写入回执 | customizations/components/godot-host/requirements_agent.py 中 design-docs 写入；design-docs/；work-items.json 的 requirements_root | 内容设计属偃师；Git 文档存储属本模块。写文件、提交、推送分别留证；与工单创建可组合但不可互代 |
| github-workorders | 稳定需求标识查重、创建／回读 Issue、类别／状态映射、来源修订及幂等对账 | customizations/components/issue-workorders/work_items.py、issue_events.py、github_source.mjs；customizations/platforms/work-management/github/git-issue/；work-items.json；.github/ISSUE_TEMPLATE/、labels.json、status-labels.json | 两套入口需按宿主选择，不双重创建；来源状态以远端为准，司南协调职责不迁入本模块 |
| github-workorder-relations | 将通用父子任务／依赖映射为远端子 Issue／关系，回读关系与修订 | 通用语义在 framework/specs/work-order-management.md；GitHub 生命周期在 customizations/components/issue-workorders/issue-lifecycle.md | 生命周期已定义原生关系及人工授权回读；当前自动适配器未实现关系迁移，不能宣称已自动接通；正文写“父单 #N”不证明 GitHub 原生关系存在，父单不得因子单完成自动关闭 |
| git-change-integration | Git 身份映射、共同基准、工作树隔离、差异／冲突、commit/tree、贡献整合 | customizations/platforms/development/git/heqi/git-workflow.md、concurrent-issue.md；customizations/components/issue-workorders/git-workflow.md | 合契保留通用整合责任；认证 login 与实际执行者关联由宿主核验，提交作者字段本身不是认证 |
| github-pr-gates | PR 关联、Issue 回读门禁、分支保护与 CI 接入 | customizations/components/issue-workorders/issue_gate.py；.github/CONTRIBUTING.md、PULL_REQUEST_TEMPLATE.md、workflows/gonggong-issue-gate.yml | 本仓库入口约定仍有效；不升级为无 Git 项目的核心前置条件。CI 文件存在不证明远端保护已启用 |
| git-delivery-evidence | commit/tree 与交付文件摘要、来源一致性、发布引用和回读 | customizations/platforms/development/git/delivery/check_delivery.py；customizations/platforms/development/git/delivery/templates/delivery.json；customizations/platforms/development/git/delivery/test_delivery.py | 现有检查器／模板是 Git 专用实现；核心只要求不可变候选、证据及实际交付回执，其他来源另行适配 |
| github-delivery-lifecycle | main 接收、Issue 完成／结转及实际状态回读 | customizations/components/issue-workorders/yanluo_host.py、yanluo_progress.py、yanluo.md、issue-lifecycle.md；customizations/components/yanluo/ | 阎罗承担当前宿主交付；GitHub 写入与关系操作属接入实现，不改通用协调、整合责任，不扩大已准入 Agent 权限 |
| git-file-telemetry | 事件文件持久化、只增不改、采集索引、index／HEAD 校验 | customizations/platforms/data-collection/git-files/storage/；issue_gate.py 的采集检查；work_items.py 的 collect；gonggong-diting-data/、data-collection/ | 共享谛听语义保留；文件落库、Git 跟踪、远端发布、消费分别证明，历史数据只读 |
| yanshi-git-ledger | 兼容偃师 CLI 的本地文档、账本、工单及 Git 操作 | customizations/platforms/document-management/git-markdown/yanshi-legacy/；framework/agents/yanshi/references/tools.md | 兼容接入组合，不是偃师本体；后续有真实替换需求时按文档、工单、版本能力继续拆实现 |

一个文件承载多个职责时按函数／流程分别归属，不能仅迁移文件夹就宣称解耦完成。尤其 requirements_agent.py 当前同时承担需求模型调用、GitHub 身份／仓库检查、Markdown 保存与建单，本次只是把这些责任标清。

## Godot 与其他环境职责

| 逻辑子模块 | 当前归属 | 责任边界 |
| --- | --- | --- |
| godot-host-ui | customizations/components/godot-host/bridge.py、HOST_PROTOCOL.md；editor/docks/ai_chat*；tools/gonggong_bridge.py | Godot 会话、面板、宿主请求与工具权限映射；界面不是核心 Agent |
| godot-project-operations | editor/ 中现有接入操作；integrations/godot/；tests/editor/ | 场景、资源、编辑器对象与测试映射；核心保留意图及验收，不承诺其他引擎同构 |
| godot-build-delivery | tools/build_gonggong_editor.ps1、editor_self_build.py、install_gonggong_editor.ps1、launch_gonggong_editor.ps1；相关发布／自更新工具与 .github 构建工作流 | 编译、产物、安装、启动、更新／回退；OS、架构、编译器和设备验证按实际需求配置 |
| host-runtime-provisioning | customizations/components/godot-host/environment_igniter.py；tools/install_gonggong_runtimes.py、configure_gonggong_runtime.ps1 | 发现并部署所选组合需要的运行依赖；Python／Node／Git 不是所有宿主的通用要求 |
| host-agent-dispatch | customizations/components/codex-dispatch/；tools/godot_parallel/ | 现有司南委托到特定宿主实例的映射；核心协调与模型选择契约保持共享，不能把宿主 CLI 当核心前置条件 |
| model-transport-adapters | customizations/platforms/ai-access/host-http/runtime/adapters.py；tools/codex_cli/、tools/codebuddy_cli/；requirements_agent.py 的传输部分 | API／CLI 协议及能力映射；供应商语法与工具限制留在接入，宿主统一治理权限 |

此表列共工接入边界，不把上游 Godot 的全部引擎模块改为共工模块。Godot 源码继续在仓库根，外部引擎目录不变；已有实现的物理拆分、平台编译、工具安装均不在本次范围。

## 契约与组合

核心语义按能力选择，不要求每个模块都提供所有接口：需求／设计输出含稳定 ID、内容、范围、决定、验收及证据；存储输出含来源标识、对象标识、不可变修订和回执；工单输出含账本及工单 ID、修订、状态、责任与关系；变更输出含共同基准、贡献版本、差异和候选；执行输出含实际目标环境、结果、产物、验证与恢复信息。来源专有字段保存在适配器映射中，不污染核心必填字段。

宿主绑定记录选择的模块 ID／版本／指纹、契约版本、配置来源、路径基准、权限、目标环境及准入证据。依赖只指向真实所需能力；例如 GitHub 工单与 Godot 不互为必需依赖。单次需求先固定绑定，变更按事件重新核对，不热替换在途依赖。未选模块不参与上下文、工具注册和验证前置条件。

新的模块目录按 customizations/components/<module-id>/ 组织；契约至少包含 module.json、按需说明、实现与适用验证。本文不新增自动扫描或加载器；未来由现有宿主按明确登记选择入口。新 skill／Agent 按现有工具及上报契约创建，不在模块中复制核心规则；涉及历史随包实现的迁移保留兼容入口直到消费者验证和精确准入完成。

## 后续接入时的最小流程

1. 偃师或当前业务主责确认目标、验收、来源、执行宿主与目标设备，保留用户原意。
2. 宿主按能力目录核对实现、兼容范围、权限和证据；司南把缺口关联当前需求。缺证、缺配置、权限不足与从未接入分别处理。
3. 可复用就绑定已有模块；仅参数不同就形成配置；真实能力缺口才生成最小子模块候选及适用工单，不预建所有平台。
4. 由已有主责完成定义和适配，必要时按框架组织规范生成受元衡管理的子 Agent 委托。模块创建与 Agent 创建不是同一动作。
5. 验证代表成功与失败、取消恢复、权限边界和未选择时的隔离；记录准确平台及未知项。审查、准入及宿主授权满足后才启用，失败保留原绑定和恢复点。
6. 将实际完成／失败、依赖变化与回执交给司南和谛听；配置、排队、落库、消费分开记录，不启动定时兜底。

结构推演（不是运行验收）：独立需求可以由偃师输出到已授权文档服务，不要求 Git 或 Godot；相同工具的新设备若契约兼容只增加配置与该设备验证；遇到全新引擎时复用需求、协调、整合、质量与采集职责，仅补所需引擎能力映射。任何新服务都需真实权限和回读，不能据此宣称现已接通。

## 新增模块的构建边界与验收

### 原生缓存的精确宿主输入清单

`tools/native_host_inputs.json` 的路径基准为仓库根。它逐文件列出已核对的独立宿主 Python 输入和说明，不接受通配符或整目录声明；目前仅准许 Tianxuan 和合契 Git 宿主路径。它不改变模块准入、运行授权或测试要求，也不直接使 CI 跳过构建。

设实际配置的 SCons 原生输入为 N，已审查宿主文件清单为 H，则仅 H 中不属于 N 的文件可排除于原生缓存身份。实际生成器/编译消费者优先于清单；新文件默认仍入键。清单文件自身始终入键，清单变更会使旧身份失效。不得仅凭 `placement: host_tool` 或文本后缀扩大排除。

本地缓存按当前工作树清单及文件字节建立身份；GitHub artifact 身份从 HEAD 的清单 blob 读取，与其余 Git tree 条目绑定，未提交清单不能改变该身份。清单损坏、非法路径、链接或 probe 失败时沿原缓存回退策略执行，不沿用旧成功证明。Windows/MSVC 缓存仍限于原支持配置，不推广到其他平台。

验证入口：`tests/editor/test_editor_native_cache.py`、`tests/editor/test_native_host_inputs.py` 和 `tools/test_windows_editor_artifact.py`。其中真实 SCons dry-run 回归验证“原独立宿主脚本被新增生成器消费后重新入键”；独立修改命中、未知新增文件/混合原生输入/策略改变失效、hosted dirty 清单隔离和损坏回退分别验证。`.github/workflows/native-cache.yml` 对适用 PR 与 merge_group 在 Windows/Linux 执行这些回归；Linux 的夹具测试不等于生产 Linux 编辑器缓存支持。

路径以仓库根解析。发现与复盘见[并行工单复用编辑器](../design-docs/engine-artifact-reuse-rollout.md)。先沿 SCsub、生成器、加载器和分发清单追到实际消费点。即使源文件是 GDScript 或 Python，只要生成的头文件进入原生链接，该文件就属于编译输入。对运行时独立读取的包，记录宿主 API 版本、可信选择入口与包摘要；编译器、SDK、生成脚本或影响原生输出的选项变化时重新判断复用范围。

| placement | 设计依据 | 必须实测的 checks |
| --- | --- | --- |
| native | 直接参与引擎编译或链接 | native_invalidation：改变原生输入后构建键失效，并验证新行为 |
| embedded | 内容经生成器嵌入可执行文件 | generated_input_invalidation：改变生成输入后验证受影响的目标重建 |
| runtime_package | 包可在既有宿主接口上单独替换 | same_binary_update、incompatible_rejection、rollback：验证新旧包行为、拒绝不兼容包、恢复旧行为 |
| host_tool | 宿主进程独立执行，说明与引擎的调用关系 | host_behavior：从正常入口运行并核对产物或回执 |
| mixed | 同一模块同时含原生和可替换业务包 | native_invalidation 及运行包的三项检查，分别列出输入边界 |

偃师或模块主责在模块根写入 `build-impact.json`，字段为 `placement`、`reason`、`host_contract`、`rollback` 和 `evidence`。evidence 是仓库相对路径，指向实测 JSON；input_blobs 将实际测试的输入路径绑定到 Git blob ID（暂存后可用 `git rev-parse :路径` 取得），覆盖模块内所有文件（分类记录和证据文件自身除外），并列出实测涉及的外部输入。checks 中每一项保留 command、observed 与实际布尔值 passed。同二进制换包的检查还保留 before_executable、after_executable、before_package、after_package 四个 SHA-256。验收者按记录复核输入、检查方法与实际行为。构建分类记录用于审查；缓存命中仍由构建器核对实际输入。

本地从已获取的目标分支核对完整候选 index：

```text
python customizations/components/issue-workorders/issue_gate.py --repo . --module-impact-only --base-ref origin/main
```

正式提交和 CI 使用相同检查。新增 Godot modules、接入组件目录、平台注册项、module.json/component.json 声明、项目插件和 GDExtension 进入核对范围。其他目录新增独立业务模块也随模块提交 build-impact.json。既有边界在引入时留存，变更构建归属或宿主契约时更新记录和受影响的验证证据。
