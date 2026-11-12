# 通用运行环境配置解除 Codex 依赖

父需求：provider-independence-20261112。用户于 2026-11-12 明确要求执行并修复全部已审计 Codex 强依赖，授权当前会话持续交付。

范围：Windows 配置入口、缺失环境恢复、宿主验证与回退。无 Codex/账号时也能从经探测的 Python/Node/Git/gh 候选确定性配置，保留原请求、治理及事务回退，失败准确报告。保留兼容入口，明确通用配置不调用模型。目标 Windows x64/PowerShell；隔离临时目录实测，代表失败及回退回归。写入责任 tools 的运行配置脚本、相关 tests、editor/docks/gonggong_panel.cpp 与本设计。其他模型服务、外部身份和马良由兄弟项处理。交付以真实测试、独立审查和 main 回读为准。

## 实现与验证（2026-11-12，#841）

实际写域：`tools/run_gonggong_config_agent.ps1`、`tools/configure_gonggong_runtime.ps1`、`tools/gonggong_runtime_policy.ps1`、`tools/test_runtime_provider_independence.py`、`tests/editor/run_runtime_setup.py`、`editor/docks/gonggong_panel.cpp` 与本文。两个策略/旧回归文件由父会话在原授权内增补派发。

通用配置不发现或启动 Codex、不读取模型配置、不扫描 Codex 私有运行库。保留旧脚本名与 `-Codex`/`-Model` 参数作为无操作兼容入口。执行探测后按项目运行库、会话显式路径、显式运行库来源、PATH、用户安装、系统安装的固定优先级选择；同优先级按路径的 OrdinalIgnoreCase 顺序选择。所有选择仍受组件路径允许列表、二次执行探测和框架 doctor 约束。治理摘要与当前委托保持强制校验；gh 缺失时只在治理校验通过后使用原校验安装器，最终委托重新绑定含 gh 的候选清单。回执明确标识 deterministic-runtime-config，provider_started=false、模型及用量 null。部署失败保留原事务回执与 rollback 状态。

编辑器去掉配置动作的 Codex/model 参数，更新文案；原需求保留、配置成功继续和回退流程沿用原实现。原生输入为 `editor/docks/gonggong_panel.cpp`，宿主接口仍为 PowerShell JSON 结果；需重新构建候选编辑器，由父会话完成编译和静默原生验收。脚本属于原有宿主工具的修改，无新增模块边界。

验证：

- `py -X utf8 tools/test_runtime_provider_independence.py -v`：4 项全部通过（实际 Windows PowerShell，隔离临时宿主）。无 Codex/账号成功、确定性重跑及配置回退、缺失组件拒绝、doctor 失败原回执保留、治理改写且 gh 缺失时在安装前拒绝均覆盖。
- 使用 `tests/editor/run_runtime_setup_simulation.py` 的 `make_package` 创建 PE 启动器包，转发本机实际 Python/Node/Git，运行 `tests/editor/run_runtime_setup.py --source <临时包> --out <临时报告>`：10 项全部通过。包括初次部署、重复使用、回退保留文件、重复回退拒绝、doctor 失败恢复、清单摘要篡改拒绝、确定性配置、治理缺失/改写拒绝及缺少 Python/Node 时编辑器启动入口探测。模型选择器 fixture 确认从未执行。
- `git diff --check` 通过。脚本改动、策略改动和回归均在指定 worktree 内；未提交、未推送。

测试边界：新用例对 Node/Git/gh 路由使用可执行 `--version` 替身；上述 PE 包回归使用真实本机 Python/Node/Git，但不是独立供应商安装包验收。未实测联网下载、GitHub 登录、原生 UI 或原请求继续执行；交由完整候选验收，不以脚本通过替代业务验收。首次新增回退用例因测试命令遗漏 ExecutionPolicy 而失败，补齐隔离 PowerShell 启动参数后重跑通过；产品代码没有通过放宽执行策略绕过验证。

复用经验：已召回 editor-dependency-handoff 已验证方法，交接准确报告实际候选字节、执行终态和验证边界；父会话须核对候选及验收证据后释放依赖，收到子任务完成不等于整体业务验收。

### 独立审查纠偏与复验

独立审查复现了 GitHub 检查器在成功部署后抛出异常会被外层失败处理覆盖、丢失路径及回退回执的问题。现将检查器执行、结果文件缺失、JSON 解析和布尔状态校验限制在独立错误处理范围内；失败输出保留 `ok=true/state=configured` 与原路径、receipt，同时写入 `github.ok=false/action_required=true/error=github_check_failed` 和实际错误详情，进度停在 `github_action_required`。

`py -X utf8 tools/test_runtime_provider_independence.py -v` 在格式化后重新运行：5 项通过（24.749 秒），新增用例包含真实 PowerShell 抛异常、无 JSON、损坏 JSON、错误 ok 类型四个情景，逐项核对成功部署回执与四组件路径均保留。ruff 自动排序曾将 fixture 导入移动到路径初始化前，复验发现后改为显式 importlib 文件加载；再执行 ruff check/format --check 和全部测试通过。

### 完整候选原生恢复链验收

父会话补充授权修改 `tests/editor/run_runtime_setup_simulation.py`、`tests/editor/run_requirements_intake.py` 与 `tests/editor/requirements_intake.gd`。完整入口最初遇到旧 Codex 文案断言，原失败日志保留在指定临时报告根的 `failed-legacy-assertion/`。已改为独立 runtime setup 场景标志、空 Codex 编辑器配置及确定性配置文案；仍放置可发现的 Codex 负调用陷阱，最终断言陷阱未启动、实际成功部署回执存在且 provider_started=false。原请求进入需求阶段、后续工单/补充/取消/修复场景的完整断言均保留。

实际命令：`py -X utf8 tests/editor/run_runtime_setup_simulation.py --godot D:/GongGong/.worktrees/provider-independence-20261112/bin/godot.windows.editor.x86_64.console.exe --out C:/Users/ROG/AppData/Local/Temp/gonggong-provider-840-logs/runtime-simulation`。完整结果 ok=true：3 项中断情景、5 项 journal 边界、10 项部署回归、11 项原生需求场景通过。真实候选 editor SHA256 为 `878d8a77952711fdc7edeaefb1b08b036178189e597c14eadade121ac5d560a6`；runtime_setup_and_resume=true、runtime_setup_provider_invoked=false、原生读取工具往返 1 次、需求调用 11 次、开发调用 7 次、隔离工单 5 个、事件 71 条、隔离 git-check committed。测试 Windows Job 已清空。

这补齐此前未测的 Windows 原生窗口与原请求继续证据；模型、GitHub 仍为 loopback/CLI fixture，无真实外部发布。报告首项旧“AI Agent”标签在同次成功执行后按真实行为更正为 deterministic host setup，并在临时 `label-correction.json` 明示只更正描述、不变更执行与断言结果。最终两份 Python fixture 的 ruff check/format 和三个测试文件 diff check 通过。

直接路径分支补验：独立复核发现 `--runtime-python/node/git` 曾只供未调用的模型 fixture 使用，可能误选 PATH。现为 direct 参数生成隔离 PE 转发源包，显式 Node/Git 路径分别进入可编辑配置和会话配置，Python 从该源包发现；不固定 GONGGONG_PYTHON，仍能实际触发 missing-python 恢复。每个成功部署回执逐项核对预期 Python/Node/Git/gh 路径。清理继承工作区环境后，用相同候选编辑器运行 direct 原生需求流程：全部 11 项通过，`runtime_setup_explicit_paths_verified=true`、`runtime_setup_provider_invoked=false`，同样完成 11 次需求调用、7 次开发调用、5 个隔离工单与 71 条事件。报告为指定临时根内 `direct-requirements-intake.json` 及 stdout/stderr/process/debug 文件。第一次未清理继承 GONGGONG_WORKSPACE 的启动被现有隔离保护主动拒绝，未运行用户工作区；改用完整模拟入口相同的 clean_env 后通过。

## 主线交付与结束回执

PR #872 已合入 main `e15a49f9b7dbbdbb1b585fc2b68cc3f252d88c8b`，签发与主线内容树均为 `b49a20e187af2a6d046e96e2c8eef67af079085a`。最终 Windows CI run43131251293 成功，运行时中断、事务、部署及原请求恢复检查重复通过。正式门禁、独立审查和主线回读完成，#841 已以 completed 关闭并回读 status:done。测试仍使用受控服务与本机工具，不外推为全部供应商安装包或断电时序覆盖。父 #840 的平台剩余项由 #843 保留。
