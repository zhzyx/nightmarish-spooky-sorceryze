# GitHub 派发运行边界统一

<!-- gonggong-request:github-dispatch-runtime-selection-20261113 -->

工单 [#994](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/994)，父需求 [#978](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/978)，依赖 #989 已由 PR #995 交付。稳定需求 ID 为 `github-dispatch-runtime-selection-20261113`；授权 `codex-user-ai-github-integration-refactor-20261112`，责任 Sail-Li。来源正文 SHA-256 为 `1d49b3d4e8d9f1c4aeb599c74e0f6df4b83cf27475e0c83e465a07df04ed59de`。以下持久路径相对仓库根。

## 已复现问题与实现

精简 PATH `/usr/bin:/bin`、环境 `GONGGONG_GH` 为真实绝对 CLI、config 未给 gh 时，旧 openSession 仍 spawn 裸 gh 并 ENOENT。repository session 的 bootstrap、权限回读、intake 分别取不同来源；显式空值还能被 `||`/`??` 回退。

新增的 `customizations/components/issue-workorders/github_runtime.mjs` 和 `github_runtime_bridge.py` 属于既有 host_tool 内部依赖。JS 用配置中的宿主 Python，以 `-I -B -X utf8` 执行由自身 import.meta.url 定位的桥接；Python 只从该桥接的真实安装目录加载已交付 `github_runtime.py`。发现与 GitHub CLI 传输都委托 #989 实现，没有新增生产发现算法。目标项目、cwd、PYTHONPATH 与伪造 sitecustomize 不能提供桥接代码。

选择优先级为本次 config 的显式 gh → 显式环境 GONGGONG_GH → 共享 Python 安装/PATH/固定位置发现。显式属性即使为 null/空值/错误类型也失败关闭；缺失或不可执行文件不回退。裸命令按传入 PATH 精确名称解析，无 PATH 不借默认路径。会话固定一个绝对路径和子进程环境，新会话会重新读取配置；保留当前账号、环境与凭据，未调用账号登录或切换。

codex operator 的 GraphQL 权限、Issue 回读共享这条连接；repository bootstrap、inspect、intake 也使用它。report 子进程继承同一个环境，并改从 report.py 自身安装根加载 Godot reporting adapter，工作区仍是事件数据目的地。每次身份、仓库及有效 WRITE/MAINTAIN/ADMIN 检查和来源修订、锁、claim、launch-intent、终态、handoff、独立验收规则未改变。

GitHub 请求使用 Python 原有 120 秒超时和脱敏错误，JS 兜底期限为请求超时加 5 秒，解析桥接为 30 秒。JSON、启动失败和超时错误不泄露原 stdout/stderr；未知写入结果明确要求远端回读。intake 与报告子进程有 120 秒等待和输出上限，失败分别要求回读 gate/远端或本地记录。没有对派发工作者追加此超时，也没有自动重试或释放在途占用。

## 宿主与构建边界

召回 `godot-build-placement` revision 16 后沿实际消费者核对：这些模块由 Node/Python 宿主运行；editor/SCsub 没有把本次新增模块列为原生或嵌入输入。没有新增组件目录、Agent、框架清单或冻结批准修改。`tools/package_workspace_release.py` 以 git archive 收录已提交文件，因此回归使用真实 Git 提交、归档、解包到带空格的新安装根，执行新桥接及已交付 Python 依赖；缺少该依赖直接拒绝。回退恢复共同候选中的消费者和三项运行边界文件；有效安装未切换。

`tools/configure_gonggong_runtime.ps1` 在 Python 安装前负责部署和探测选中的依赖；它在依赖就绪后才执行 doctor。`install_gonggong_editor.ps1` 先经 run_issue_gate.ps1 探测 Python。此处是 provisioning 边界，不改为依赖完整 Python GitHub 运行时。本机未执行 Windows 安装，未声称 Windows 现场验收。

复核 reporting 的 host_environment 时曾推测 legacy 状态会覆盖 GONGGONG_GH；进一步读取真实 schema 后确认 igniter 只有 Python/Node/Git，runtime_config 只有 Node/workflow Python/build Python/Codex。该推测不成立，没有扩大 bridge 公共接口。实际回归写入隔离的合法 legacy Node/Git 状态，使其 PATH 包含另一合成 gh，证明显式绝对 GH 保持优先，Node/Git 初始化和父环境均保留。

## 验证、局限与交接

准确命令、结果和输入 SHA-256 见 `data-collection/github-dispatch-runtime-selection-994.json`。真实只读复验使用原 PATH 与宿主绝对 CLI，openSession 对真实账号 Sail-Li 和目标仓库的写权限回读成功，config 仍没有 gh；没有启动工作者或远端写入。合成端到端覆盖 bootstrap、intake、权限恢复和真实 Diting 本地记录，恶意目标项目未执行。权限撤销、外来 claim、handoff、worker receipt、launch-intent 与独立验收原断言保留。

验证中既有框架子进程因测试 PATH 无 Node 首次失败，补入已知宿主 Node 后通过；新增 GUI fixture 首次漏 defaultChatModel，被原校验拒绝后补完整。扩大 acceptance suite 暴露 macOS /var 与 /private/var 别名，单独修正 fixture 的真实路径，不改生产权限判定。mypy 检出旧 report import spec 可空，补显式拒绝，未降低类型检查。

测试临时目录均由各测试回收；本任务生成的 Python bytecode 和临时日志在证据归档后清理。保留此隔离工作树、未提交候选和验证证据供根会话接收。根会话负责独立审查、正式门禁、精确 CI、提交/推送/main 和工单回读。本实现阶段不声称 #994 已关闭，也不代表 #978 整体验收。
