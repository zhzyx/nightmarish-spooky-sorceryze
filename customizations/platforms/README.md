# 按平台接入共工

[目录清单](catalog.json)以仓库根为路径基准。先选能力类别，再选择实现平台。例如只将设计存入 Git 时，调用文档适配器即可；需要创建 GitHub 工单时，再接入工单平台。一个宿主可组合多个类别。

| 类别 | 当前职责与入口 |
| --- | --- |
| [过程管理](process-management/repository/execution-policy.md) | 仓库事件、工作树交接、检查和交付顺序。司南保留派发与依赖协调职责。 |
| [文档管理](document-management/git-markdown/requirements.py) | 偃师给出设计，适配器写入 Markdown，返回相对于仓库根的文档路径。 |
| [数据采集](data-collection/git-files/event.template.json) | 谛听定义事件语义，[Git 文件适配](data-collection/git-files/storage/README.md)负责存储与提交状态。 |
| [工单及项目进度](work-management/github/issue-lifecycle.md) | GitHub Issue、子项、状态、回读。目录内有来源适配器与可选建单器。 |
| [开发平台](development/git/git-workflow.md) | Git 版本、工作树、协作者身份和 GitHub PR/CI。[交付检查器](development/git/delivery/check_delivery.py)核验清单和证据。 |
| [游戏引擎](game-engines/godot/host.md) | Godot 编辑器、桥接、场景、构建及安装。引擎原生代码按构建系统布局。 |
| [AI 模型](ai-models/daqian/environment-providers.json) | 大千用环境变量发现供应商型号，本机模型库维护能力、评测和选择。 |
| [AI 接入方式](ai-access/daqian/http_protocols.py) | 大千 HTTP 请求与响应协议。CLI、HTTP 与宿主派发可服务于同一模型。 |

## 主线文件归属

| 范围（仓库根） | 如何处理 |
| --- | --- |
| CURRENT_FRAMEWORK.json、framework/ | 指针定位共享纲领、治理、Agent 职责、契约与准入。本仓库选用的宿主实现见下表及各平台目录。 |
| customizations/、integrations/、tools/ | 宿主组合、适配实现和调用入口。现行宿主组件清单为 [components.json](components.json)，Agent 委托由 host-agents 管理。旧 customizations/registry.json 保留为既有版本的引用。 |
| .github/、Git 根配置、work-items.json | Git/GitHub 开发与工单平台发现的位置。CI 在 .github/workflows，模板在 .github/ISSUE_TEMPLATE。 |
| design-docs/、仓库根的研究与构建记录 | 文档平台的业务内容与历史记录。 |
| data-collection/、gonggong-diting-data/ | 采集来源、回执和事件数据。 |
| core/、doc/、drivers/、editor/、main/、misc/、modules/、platform/、scene/、servers/、thirdparty/、tests/、project/、samples/，以及根目录的 Godot 构建与发行文件 | 引擎源码、第三方依赖、样例、开发工具及测试。这里的 core/ 是 Godot 核心。 |
| archive/、releases/、distribution/、olympus-hermes-data/、framework/reviews/、framework/upstream/ | 归档、发行证据、历史事件及上游原件；溯源时按其原路径读取。 |

## 迁出的现有宿主

| 选择的能力 | 实现与入口 |
| --- | --- |
| 过程管理 | [本地来源和派发](process-management/yuanheng-local/sinan/module.json)，由宿主绑定来源、容量和回执。 |
| 工单管理 | [GitHub 后续工单关联](work-management/github/follow_up.mjs)，与本地进度适配组合。 |
| 文档管理 | [偃师版本化文档与账本 CLI](document-management/git-markdown/yanshi-legacy/README.md)。 |
| 开发平台 | [Git 变更整合](development/git/heqi/git-workflow.md)、[P4V](development/p4v/p4v.md)、[Git 对象读取](development/git/git_batch.py)。 |
| AI 接入与模型评测 | [本地 HTTP 执行宿主](ai-access/host-http/runtime/README.md)，组合模型能力评测与共享谛听上报。 |

新接入在对应类别下以平台名建目录，声明依赖、读写对象、权限、输入输出、失败恢复、验证与撤销方式。下游引用能力输出，例如文档修订或工单回执。宿主选择实现并核验准入后才执行。目录清单仅用于发现；原平台批准随原精确候选留存。
