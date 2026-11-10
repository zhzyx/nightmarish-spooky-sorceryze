# 天枢与共工工单入口清查

父单 #748，子单 #749，需求 ID `editor-issue-path-audit`。普通工单聊天及 flush 的安装来源由 #747 交付。复用本租户 `editor-dependency-handoff / bind-consumer-release` 第三版，父单接收时核对本次实测的 EXE、资源包与 PR 候选。路径均相对本仓库根。

| 操作 | 实际入口、选取来源 | 本次核验 |
| --- | --- | --- |
| 环境、工单绑定及共工工具 | `editor/docks/gonggong_panel.cpp` 保存工作区、Python、租户、Issue 编号与需求 ID。状态、诊断、完整性检查、校验、分析及点火器回退经所选工作区 `tools/gonggong_bridge.py`；配置 Agent、运行库回退及登录由安装侧 PowerShell 启动。 | 私有工作区实按六个动作，逐项核对传给子进程的 action、工作区、租户和输出回显。设置探针还验证编辑、切换、旧工作区清理。外部登录和真实部署回退未执行。 |
| 看板、检索、图导航、详情及存稿 | `workspace.gd` 核验协作者后调用工作区 `board.py`、`graph_host.py`、`models_cli.py`。进度与调试使用工作区 `watch_progress.mjs`、`debug_session.mjs`。两份已知旧看板哈希使用编辑器内置只读投影，复核选中工作区的脚本。图展示资源由安装包或显式 SHA-256 选包提供。 | 原生 55 单图、身份切换、离线、拒绝、详情编辑撤销、保存重开、模型入口、并行、输入、多个工单。旧版、改过的旧脚本和带 delta 的工作区选路通过。相同 EXE 的安装包、候选、回退、错 pin、损坏等 11 案通过。 |
| 工作流、建单、重试、需求判断、推进 | 天枢需求表单经 `issue-direct`，判断经原生 `_launch_daqian_routing` 调用工作区桥的 `issue-route`，开工经 `issue-start`。手动入口保存的需求与预期账号、来源及回执绑定。 | 真实控件与私有子进程覆盖创建确认、未知回执先回读、失败后重试、切换工单时返回、二次进程恢复、判断和澄清。 |
| 画布与审批 | `canvas_context.gd` 的 TextEdit 收到 Enter 后，`workspace.gd` 核验作用域，原生 ChatDock 发送预览。命令卡片核对原账号、Issue、request、源码及候选。 | 本地 HTTP 实际收到单工单 Enter。切到总览再回到原单收到答复，401 和过滤响应各自收尾。换账号、过期卡、失效 cwd、重复确认、两个独立工作树、停止一单、重开待批准命令和执行期恢复均走原生入口。 |
| 记录、来源和交付 | 原生 `ai_chat_gonggong.cpp` 绑定事件来源与 outbox；聊天和 flush 优先安装桥。候选来源由 `editor_engine_candidate.py` 验证；`complete_delivery` 的权威结束来自签发、PR/main 及 Issue 回读。 | 双工单真实 recorder/flush 取得两条独立执行回执，一单取消、一单仅写一次。finalize 的 15 项主机测试通过。本单发布用真实 writer_submit。Windows 上两项 POSIX 专用原生交付夹具止于创建 symlink，未把本单签发算作这两个模拟场景通过。 |

## 缺陷与边界

Windows 工作流选择 venv 时，CPython 每次启动不同的重定向进程。旧看板以直接父 PID 与每次编辑器的随机 nonce 定位缓存，首次验权后下一次读取会误报登录切换。当前宿主仅在确认父进程镜像恰为已配置 venv 的 Python 启动器时展开一层，登录、仓库、nonce 和账号复核仍照常工作。选择仍含旧 `repository_access.py` 的工作区时，本修复需要交付至该宿主路径。旧版看板投影测试覆盖来源选择，并未验证任意历史工作树上的写操作。

审批探针此前在 Windows 私有安装启动后才填写工作区，且缺少 Node，使单工单 Enter 没有送到已聚焦的 TextEdit。将私有工作区与 Node 在启动时配好后，同一二进制的原测试直接通过。键盘断言仍通过视口真实送键。简化 Python 环境缺少 pip 时，图探针复用 ensurepip 自带的 wheel 生成 Windows fixture-gh。

权限、判断和模型服务使用本地夹具。安装包与源码未通过本工作修改用户桌面。设置行为全部通过；严格退出报告含 RID 泄漏与调试器提示，由父单接续。POSIX 专用用例和 Windows 符号链接权限覆盖缺口、候选及来源测试统计见[验证记录](../data-collection/editor-issue-path-audit-749.json)。#753 绑定本次原生故障与复验。
