# Godot GongGong 宿主适配器

## 静默验证

所有协作者默认在后台验证 Godot 变更。使用候选编辑器的 `--headless`、隔离项目、控件信号和几何断言。不要通过电脑控制驱动用户桌面、切换焦点、移动鼠标或发送按键。碰到只能由真实显示器复现的问题，记录具体缺口，留给用户自行检查。

首次启动带此接入的编辑器时，它用同一可执行文件和临时项目在后台实际运行 GDScript 控件探针。子进程成功退出并返回预期结果后，编辑器才在本机用户的编辑器缓存目录写入 `godot-silent-*.ok`。更换构建路径、构建版本、文件修改时间或探针内容时重新校验。失败、超时或启动中断会在下次打开时重试。修复宿主或可执行文件的 headless 支持后，应取得成功回执再使用该环境验收。

探针验证后台运行能力。业务变更仍需跑对应场景。例如在仓库根运行 `python tests/editor/run_daqian_graph.py --godot <候选编辑器路径> --scenario graph --report <本机报告路径>`，检查大千入口、图交互和布局。

`bridge.py` 是唯一 Python 实现；引擎通过 `tools/gonggong_bridge.py` 调用。原生页面在 `editor/docks/gonggong_panel.*`，发送控制在 `editor/docks/ai_chat_gonggong.cpp`。

开发前先创建或复用 `work-items.json` 对应仓库的真实 Issue，在 GongGong 页面填写 Issue 编号和工单中的稳定需求 ID（修改即保存到本机）。IDE/CLI/生产工具在 chat 协议中传入整数 `issue_number` 和稳定 `request_id`，不再以聊天快照生成需求 ID。每轮先回读真实 Issue，核对 origin、租户、唯一类别、唯一 in-progress/in-review 状态、需求 ID 和 workspace:gonggong；失败或离线拒绝执行。工单本身不产生工具权限或 Agent 准入。创建工具仍需显式发布确认及真实权限；未建单不能先开发再补单。

宿主文件事件的来源绑定真实 Issue URL；上下文尝试追加 request 事件并保留快照摘要，不采集用户原文。采集文件入库后仍未提交，交付必须把 data-collection 来源/验证/回执及 gonggong-diting-data 事件与实现一起审查、暂存、提交，再执行提交后 git-check --require-committed。不得仅提交代码、把 ignored/untracked 数据当成功，或把 Git 提交当作谛听已消费。工程规则由根 AGENTS.md 和 issue-workorders 组件承接，不改写冻结的上游框架包。

每次模型请求（含工具继续轮）均调用当前工作区的 `framework/tools/agent-context.mjs`。它核对有效共工源、内容指纹、冻结纲领、Yanshi 准入和上报契约，再装配相关上下文。上下文加入 HTTP 请求的 system 内容；CLI 会话以其摘要判断是否需要重建，因此不会沿用过期框架上下文。未通过校验、缺 Python/Node、数据记录失败均不发送模型请求，没有跳过开关。

用户点击发送建立当前聊天委托；工具许可取自 Godot 实际开关，框架文本不增加本地工具权限。定义准入仍由框架校验，不由发送按钮批准。当前没有可使用的已批准 GongGong Agent 通行证，生产聊天会明确报告阻断。

运行前绑定租户、需求、来源、真实 Yanshi 定义快照、授权引用、持久 outbox 与文件数据源。记录上下文尝试、请求开始、用户/模型/工具消息元数据、模型和工具步骤、结束/失败/取消及覆盖说明。运行中的步骤由后续事件 supersedes；不把提示词、输出原文、API 密钥或本机路径写入 Git 数据。模型内部推理、流式正文和实际 token 用量未采集，用量保持 null 并注明原因。

事件先原子写入 `.gonggong-outbox/chat/`，拿到 `diting_files.py record` 回执后删除队列文件。失败保留原事件身份并幂等重试；跨进程文件锁防止结束投递与下一轮检查竞争。单次 flush 总预算 15 秒。后续模型和工具操作要求前置回执；结束/取消投递异步执行，停止先取消执行再排队。`queued`、`recorded_file`、Git 已提交是不同状态。事件进入 `gonggong-diting-data/` 后，需随对应真实需求提交。

本机可在忽略的 `.gonggong-local.json` 配置上游位置，字段示例见仓库根 `.gonggong-local.example.json`；相对位置以工作区根解析。框架自身 binding 相对 GongGong 框架根解析，与进程工作目录无关。位置配置不产生授权。上下文固定使用现有 Yanshi 设计与生产职责；未把通用 UI 会话标签当成新注册 Agent。

恢复结果先保留在原重启 journal/report 中，重验框架并获得真实绑定和回执后才接续；拒绝时保留日志，可修复配置后重试。恢复期间锁定会话/模型后端/快照切换；停止表示明确放弃恢复。验证包括正常传递、拒绝、迟到取消、工具多轮、恢复成功/拒绝，以及取消恢复后新请求。成功传输模式使用临时合成上下文入口，不修改真实框架，不产生生产准入或生产数据。

回退：恢复前一已验证二进制和对应源提交；保留事件、用户项目及采集索引。不得通过移除准入检查恢复生产聊天。


当前普通对话由 Yanshi/ClarifyFeature 的 `issue-agent` 入口先整理新需求或续聊，再自动创建/复用真实Issue；技术故障先修复并恢复原需求。需求整理是无生产工具的前置阶段，开发仍受真实工单门禁。完整协议与私有stdin凭据、重放/取消边界见 HOST_PROTOCOL.md。

## macOS 编辑器启动验证

打开项目进入定制编辑器时，共工会检查当前构建的本机验证回执。首次使用、构建或探针变化、上次失败时，在后台验证 AI Chat 入口；回执有效时直接复用。从 Finder 打开应用和从命令行进入编辑器共用此入口。探针使用同一可执行文件的临时副本、独立编辑器设置及空白工程，以 `--headless --editor` 验证标签位置、标题、图标、主题色和切换后的聊天输入框。主窗口可以继续操作。退出编辑器会终止在途探针并清理临时目录。

编辑器输出中的 `GongGong macOS startup validation passed` 表示入口检查通过，`GongGong macOS startup validation reused` 表示复用了成功回执；失败时同一前缀给出失败步骤。无窗口、脚本、命令行工具与恢复模式启动跳过自动探针。像素、原生窗口焦点和实际显示缩放仍需按对应工单验收。
