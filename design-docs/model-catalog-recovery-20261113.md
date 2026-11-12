# 模型目录恢复与推理隔离

<!-- gonggong-request:model-catalog-recovery-20261113 -->

关联 Issue #992，父需求 #978。路径以仓库根为解析基准。基线 main `a3b1ef65968f9f7d9dcdf701ae5e76feb94d9c3f`，保留 #980 的 API 凭据目标绑定。

## 需求与边界

模型目录查询须能明确刷新、取消、失败重试；目录操作不锁定发送、设置、手动模型选择、新建或切换会话，不占用对话 CLI。配置、登录或取消后的旧回调不得改变当前目录或模型选择。实际模型 ID 保持字符串类型，目录来源与供应商声明的能力保留。

#971 的每会话及马良节点模型持久化由另一操作者负责，本单不改变其设计或工作副本。个人模型库的验证、注册和凭据保存仍由已有 `models_cli.py` 接口负责；本单只迁移它读取原生配置的方式，不把目录枚举当作真实推理或账号可用证明。

## 实现契约

原生 `AIChatDock` 提供主线程接口 `get_model_catalog_snapshot()`、`refresh_model_catalog()`、`cancel_model_catalog()`；保留 `get_daqian_models()` 作为兼容代理。快照提供 backend/current/options/state/status/loading/generation/catalog_current，不导出内部身份指纹和凭据。options 从目录数据构建而非遍历 OptionButton，深复制后返回，过滤非字符串、重复或非法 ID；手动 ID 和 CLI 默认项标明来源。快照仅导出经过类型校验的 id/name/description/is_default/reasoning_efforts/source/label；保留来源与声明能力，不透传供应商附带的任意账号或 apiKey 字段。

目录拥有独立 `HTTPRequest`、CLI PID/管道、50ms Timer、输出上限、35s CLI 上限和 generation；不使用推理的 request_generation、cli_process_id、cli_stdout 等，不调用 `_set_busy()`。取消只回收本目录资源。原生向两个内置 bridge 传入 `--host-process-group`：POSIX 子 CLI 留在 execute_with_pipe 建立的组内，Windows 建立/复用 kill-on-close Job。bridge 发出终态 JSON 行后保持 stdin 与组首进程存活；原生读取后复用进程树终止设施收尾，避免先杀 bridge 而留下 detached CLI。编辑器管道 EOF 也关闭该自有组。默认非原生 bridge 调用行为保留。查询完成只替换可选目录，保持当前会话的模型输入框权威；即使当前模型为空，也不自动选中返回的第一项。

查询冻结 backend、完整有效运行配置及其来源、服务目标、目标绑定后的 API 凭据摘要、代理、相关环境身份和本地登录代次。响应仅在目录代次及当前身份一致时应用。共享配置文件或环境发生变化时，迟到响应被丢弃并按新配置刷新。编辑器内发起/完成登录推进进程内共享代次，使各工单工作者的本地目录身份失效；不读取 CLI 原始凭据文件，也不声称外部任意账号切换可自动检测。

自动启动/配置/登录事件继续去重，失败不会自动循环。显式按钮/API重试不受已消费事件位限制。取消会停止当前查询、状态检查和待处理的配置刷新。失败状态区分路径、网络/响应、鉴权、限流、超时和 CLI 拒绝，给出可执行重试或手动填写模型 ID 的步骤。

移除 AgentSession 中从未用于恢复的目录副本，所有会话从当前身份对应的唯一缓存取目录。HTTP 空模型保持显式未选择占位，第一项必须由用户明确选择。

大千 workspace 的目录消费者迁移到稳定快照；model_settings 不再爬取 AIBackend/APIEndpoint/CLIEntry 等控件，改读原生配置与有效运行时。保留其明确的账号模型验证流程。

## 验收与证据

- 原生 macOS arm64 dev editor 静默构建；不替换有效应用，不启动 GUI。
- `run_model_autofetch.py` 的 CLI/API recovery 真实异步 fixture：计数失败、用户重试、取消与再试、共享配置/环境变化、迟到结果；查询期间手动选模、新建/切换会话、发送并等待真实 fixture 推理结束；目录完成不能提前解除推理忙态。
- 真实进程边界 fixture 记录 bridge、CLI、忽略 SIGTERM 的孙进程 PID；取消后核对全部退出。另以 SIGSTOP 冻结真实 bridge，使 JS 的30秒计时器无法运行，验证原生35秒上限关闭整个自有组。POSIX此项实测；Windows Job/树边界留给对应平台 CI，不声称已本机运行。
- 既有 startup、登录、登录状态超时/延迟轮询、后端切换及会话目录新鲜度用例复验。
- `model_picker.gd` 使用真实刷新 API，移除向后端 OptionButton 发送 pressed 的错误操作；Python runner默认使用合成 app-server并记录 CLI/API请求数。供应商能力和字符串 ID 使用真实边界传输。
- HTTP取消延迟、项目设置多模式、大千原生图及画布消费者回归。
- 编译迁移漏点与旧图 fixture 缺少隔离宿主布局分别保留失败/复验证据。图 fixture 复制当前候选的实际 SConstruct、tools/customizations及独立HOME；不提升成员权限或修改产品检测。

公开汇总位于 `data-collection/model-catalog-recovery-992.json`；本地原始回执和构建日志位于 `data-collection/receipts/model-catalog-recovery-20261113/` 与 `bin/catalog-*.log`。独立审查、正式门禁、精确 CI、main 回读和工单关闭由根责任者继续，当前实现者不执行远端写入或交付。

## 临时资源

测试使用隔离可执行文件、临时项目、合成 CLI/HTTP 服务和独立设置；结束后回收其临时目录与明确归属的 fixture 子进程。保留本候选源码、构建产物和必要失败/成功回执供根责任者审查交付。实现辅助脚本与一次性编辑片段在交接前清理；不清理其他工作树、有效安装和其他工单资源。

## 独立审查与修复复验

独立审查复现了外部共享配置在 Codex 登录状态检查期间改变导致的恢复缺口。现对登录状态和待派目录的来源不匹配统一恢复当前来源，新增直接替换配置文件且不触发界面信号的回归：旧二进制确实失败，修复后原独立复现及完整19项目录矩阵通过。整合 GitHub 接入主线后重建候选，picker、HTTP取消、大千graph、外部状态竞态复验通过。历史18项实现者证据保留，后续修复/审查/新主线证据见 `data-collection/model-catalog-recovery-review-992.json`。


## 精确 Windows CI 消费者修正

PR1000 的 Windows 原生需求录入已取得目录，但旧测试硬匹配中文“模型列表已获取”，导致前置条件误报。五个驱动改用目录结构化 state/current/loading；原交互、超时、授权和业务断言保留。批次目录用例改为明确握手，验证目录未返回时业务继续，业务 Stop 与目录 Cancel 互不代替；七项目录用例及普通批次、终态存储失败两项控制均已实测通过。终态证据绑定确切来源、请求、工作序号和排除旧事件的回合边界，回读真实存储与哈希。旧 --expect-stalled 明确退役。外部并行验收包装器继续检查自己的工作者生命周期，去除串行目录测试的无关等待。

追加事实见 data-collection/model-catalog-ci-consumers-992.json；原 native C++ 和已审二进制未变；真实并行实测另发现关联 #1005 的 Node 执行器链接入口静默退出，最小入口修正在同一候选中单独留证。新候选须重新取得 Windows CI 和 main 回读，不能用本机 fixture 代替远端验收。
