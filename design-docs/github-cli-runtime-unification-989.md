# Python GitHub CLI 运行边界统一

<!-- gonggong-request:github-cli-runtime-unification-20261113 -->

- 工单：[#989](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/989)
- 父需求：[#978](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/978)
- 稳定需求 ID：`github-cli-runtime-unification-20261113`
- 授权：`codex-user-ai-github-integration-refactor-20261112`；本实现交接责任人 Sail-Li。
- 路径基准：下述路径均相对本仓库根。来源正文 SHA-256：`950a16b2801f33dfc54622cefcf3b9084b4b16518e07d116e18e1b1ecfff429f`。

## 问题与范围

原复现为 GUI 精简 PATH 下 `work_items.gh("version")` 报工具缺失，导入 `repository_access` 后却成功；导入时把个人安装写进进程 `GONGGONG_GH`，桥接和签发又各自解析。目标是 Python 宿主各入口得到相同、可解释的选择，并保持账号、仓库权限、精确候选与发布回执规则。

实现位于既有 `issue-workorders` 接入组件，未新增独立模块、组件目录、注册或 Agent 定义。`github_runtime.py` 是 `host_tool` 内的共享 Python 依赖，以当前已安装文件的 `__file__` 推导可信根。没有修改冻结框架或有效安装。

## 接口与消费者

解析顺序为显式 `GONGGONG_GH` → 可信宿主安装的 `project/runtime/gh/bin/gh[.exe]` → 调用环境 PATH → 当前平台固定安装位置。显式空值、缺失、非可执行文件均失败，不能回退；相对显式路径按调用进程 cwd 转绝对路径。缺 PATH 不借用父进程默认路径。POSIX 固定位置为用户 `.local/bin`、Homebrew 和 `/usr/local/bin`；Windows 为传入环境的 ProgramFiles/GitHub CLI 及既有用户 Codex tools 安装。Windows 路径不在 POSIX 当前目录下被当成相对安装根。

| 消费者 | 行为 |
| --- | --- |
| `work_items.py` | 保留 `gh` 与 `GitHubCommandError` 接口，委托共享解析和传输，支持 stdin JSON |
| `bridge.py` | `find_gh` 保留返回路径/None 的探测接口；root 不参与可信工具选择；明确配置错误、运行/网络/超时错误保留原因 |
| `daqian/repository_access.py` | 删除导入时环境修改；沿用工单入口 |
| `writer_submit.py` | GraphQL 沿用工单传输，Git credential helper 绑定同一解析结果并进行 shell 引用 |
| `kuafu_github.py` | POST 与原有读取共享 CLI；错误不泄露 stderr/凭据，未知写结果仍需回读 |
| `yanluo_host.py` | 实例绑定 CLI；GitHub 命令共享错误处理；签名密钥不传给子进程；可信清单新增助手 |
| `editor_candidate_activation.py` | 从安装根加载 writer，候选 source_root 仍只作数据来源；PR 回读共享工单入口 |
| `acceptance.py`、`project_integration.py` | 既有调用取得 bridge.find_gh 的共享结果，无独立工具发现规则 |
| `issue_gate.py` | 常驻会话同时核对已加载 work_items 和 github_runtime 字节，改变后失效并重启 |

`run_gh(*argv, env=None, input_value=None, cwd=None, timeout=120)` 返回去除外围空白的文本。错误区分 `GITHUB_RUNTIME`、`GITHUB_TIMEOUT`、`GITHUB_NETWORK`、`GITHUB_HTTP_*` 与普通命令失败，不原样回显子进程输出。解析与传输不修改父进程环境；桥接原有显式 `gh_state` 操作仍将本次选择交给同进程工单调用，导入没有该副作用。代码不调用 auth login/switch，不修改账号或全局 Git 配置。

## 构建与可信边界

已召回 `godot-build-placement` revision 16，按实际消费者核对：`editor/SCsub` 的 Python 嵌入清单不含本次助手、work_items 或 repository_access；它们由已安装宿主解释器单独读取。`tools/editor_engine_candidate.py` 以自身安装根加载工单门禁；`editor_candidate_activation.py` 仍核对私有 binding、来源 root、Issue/PR 和已提交源摘要，本次仅替换 GitHub 回读传输。

`tools/package_workspace_release.py` 用 `git archive` 纳入已提交源树，因此助手必须与消费者在同一候选交付。新增回归将实际助手、work_items、bridge 及其现有加载依赖写入隔离 Git 仓库，归档解包到带空格的新根，以同一 Python 可执行文件实际导入、调用合成 CLI，并证明目标项目不能替代工具根；删除助手后导入失败。CLI 安装、替换及删除在同进程下一次解析可见，无发现缓存。回退应恢复共同候选中的消费者和助手；缺依赖不猜测另一实现。此项不是新增 runtime_package/原生 ABI，未通过换后缀推断可免构建，也不声称执行了新的编辑器二进制验收。

`integrations/gonggong/frozen-distribution.json` 的 host_files 不登记这些可变接入文件，未改冻结注册。`customizations/registry.json` 仍沿用既有 issue-workorders 组件。阎罗自己的 `trusted_files` 现纳入共享助手，旧 grant 缺清单即失败，正式交付须取得新精确候选的真实签发。

## 验证与交接

原 37 项 work_items/writer_submit/issue_guide 回归、共享助手合成测试、桥接/发布/常驻门禁等受影响测试的准确结果与源文件摘要记录在 `data-collection/github-cli-runtime-unification-989.json`。合成执行涵盖导入顺序、显式失效、权限错误、PATH/固定位置/可信安装优先级、路径特殊字符、安装后重试、CLI 替换、错误脱敏、GraphQL/POST stdin、实际 Git credential helper、隔离归档与常驻失效。测试凭据均为占位值，不执行账号切换或生产远端写入。

首次手工 intake 缺 tenant 导致门禁自动登记阻塞并触发上报；补齐 tenant 后真实 intake 成功。incident `ec3e0545ca05f479ba2abbb58b41af9ff9ae8c5e0e120f6792e9d78e63d3fc12` 已交根会话接收；后续合成测试设置 `GONGGONG_KUAFU_LOCAL_ONLY=1`。首次扩展测试遇到旧 monkeypatch 目标及 Node 缺 PATH；前者随共享入口更新，后者使用已知宿主 Node 后复验。扩展回归还修正了 macOS 临时路径别名的两个 fixture 比较，并更新既有 session fixture：候选仓库的工具变更不能替换已安装的可信 validator，错误数据仍清空证据缓存。未将这些失败写成首次通过。

分配实现交接时未执行 commit/push/merge，不代表 #989 交付或 #978 整体验收。根会话已整合 main `a3b1ef65968f9f7d9dcdf701ae5e76feb94d9c3f`，补齐 `.github/scripts/windows_editor_artifact.py` 两处工具调用：JSON 走共享传输，ZIP 保留二进制流和原有 SHA-256 校验，绑定同一解析器且增加下载超时。额外9项制品测试通过，包括空 PATH 下实际执行带空格的显式 CLI，以及无效显式配置不回退。接续独立 review、正式门禁、精确 CI、main 和工单回读。

独立平台 `customizations/platforms/work-management/github/git-issue/issue_create.py` 提供显式 `--gh` 接口，module.json 默认禁用且等待精确迁移准入；README 写入示例已明确传路径。此次只读搜索未找到生产 Python/JS/C++ 宿主调用者，不反向引入 repository components 依赖。原生账号可用性、JS 与 PowerShell 宿主入口由父 #978 的相应范围承担。

测试临时目录均由 TemporaryDirectory 回收。保留本隔离工作树、未提交候选及必要来源/验证证据供根会话接收；有效安装、其他工作树及别人的临时资源未动。
