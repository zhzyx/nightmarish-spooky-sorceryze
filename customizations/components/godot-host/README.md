# Godot GongGong 宿主适配器

## 静默验证

所有协作者默认在后台验证 Godot 变更。使用候选编辑器的 `--headless`、隔离项目、控件信号和几何断言。不要通过电脑控制驱动用户桌面、切换焦点、移动鼠标或发送按键。碰到只能由真实显示器复现的问题，记录具体缺口，留给用户自行检查。

首次启动带此接入的编辑器时，它用同一可执行文件和临时项目在后台实际运行 GDScript 控件探针。子进程成功退出并返回预期结果后，编辑器才在本机用户的编辑器缓存目录写入 `godot-silent-*.ok`。更换构建路径、构建版本、文件修改时间或探针内容时重新校验。失败、超时或启动中断会在下次打开时重试。修复宿主或可执行文件的 headless 支持后，应取得成功回执再使用该环境验收。

探针验证后台运行能力。业务变更仍需跑对应场景。例如在仓库根运行 `python tests/editor/run_daqian_graph.py --godot <候选编辑器路径> --scenario graph --report <本机报告路径>`，检查天枢入口、图交互和布局。

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

## 已确认原完整任务的阶段接续

此入口只覆盖操作者明确确认、原完整验收能逐项映射到现有生产工单的父会话。普通聊天、仅咨询、独立审查和子工作者仍使用原契约。`closed`、模型的完成声明、磁盘中的 `done.json` 或仅有部分工单均不构成完整验收。

生产使用步骤（路径以当前绑定工作区为基准）：

1. 在 `design-docs/<request_id>.md` 保留既有「设计定版确认」「生产工单」格式，各工单逐行声明 `验收: ID | 可验证要求`。确实要启用完整任务接续时，在文档加入 `<!-- gonggong-parent-completion:v1 -->`。完整设计需包括原任务的全部验收和实际交付要求；不能把部署、main 接收或人工保留决定从原范围中删除。
2. 核对原需求后，由有权协作者通过现有 GitHub Issue 编辑入口，在**原 Issue 正文**增加一个 `gonggong-parent-contract` 代码块。示例如下；`design_sha256` 是最终设计文件的原始 UTF-8 字节摘要，不是下列 JSON 的摘要。`criteria` 必须逐项且唯一覆盖全部工单的全部验收 ID、原要求文本与工单编号，至少有一项真实交付要求标为 `delivery`。原始验收 ID 与工单内 ID 可以不同，映射必须明确。
3. 在已绑定该 Issue/request 的父会话发送一次正常生产消息以回读原工单；然后在现有「按工单落地」原生确认框核对完整设计与验收映射并确认。确认绑定本次实际回读的 GitHub 账户与来源，不从历史恢复。原 Issue、设计或账户此后变化时，应先回读并重新核对，不能用旧确认继续。

```gonggong-parent-contract
{
  "version": 1,
  "scope": "complete-original-task",
  "request_id": "example-task",
  "issue_number": 123,
  "design_sha256": "替换为已核对设计文件的64位SHA-256",
  "criteria": [
    {"id": "original-function", "order": 1, "criterion": "function", "requirement": "功能通过指定实测并保存原始结果", "kind": "acceptance"},
    {"id": "original-delivery", "order": 2, "criterion": "delivery", "requirement": "完成原任务要求的交付并保存权威来源回执", "kind": "delivery"}
  ]
}
```

安装宿主会再次回读 Issue、实际账户及写权限，核对确认时的完整原始来源、设计摘要和唯一映射。确认后通过现有父会话生产入口运行一个准备阶段；HTTP 和 CLI 归一化终答进入同一检查。检查在清理及回合终态前异步执行，并在消费动作前再次回读权限、来源、候选和真实工作者状态。只有已登记的可执行工单会交给既有派发器；其独立只读验收、一次纠正、依赖放行和实际完成事件继续由原宿主负责。

完整结果只来自全部映射工单的**当前 live 独立验收**。每个父终答都重新检查候选；验收检查和历史落盘尚在运行时，等待其实际完成事件。父任务 `parent_business_accepted` 与模型回合结束分别记录，不把后者当交付。声明了 GitHub/main 交付的任务，仍必须有对应真实交付执行及独立验收；本入口不会替操作者跳过发布或分支保护。

缺映射、人工保留决定、工具权限变更、取消与冷启动均不自动执行。未知副作用保留原回执并进入 readback-required；不重复工具/PR动作。相同执行和独立验收事实下最多两次无进展重返，聊天/审计文字或未验收的代码变化不算进展；超限交给既有夸父事故路径一次。运行期间只响应已有工作者、验收和持久化完成事件，不新增周期扫描；关闭进程后不承诺自动唤醒。已发出的远端操作不能被本机取消倒销，仍须核对其原回执。 原生停止、超时和编辑器关闭先撤销 mapped delivery 的 live request；安装 adapter 随后关闭自己持有的嵌套进程组/Job，保留原请求归档供只读回读。macOS 的退出状态查询使用系统 libproc，避免保护环境拒绝 setuid 进程查询工具而阻塞正常收尾。

已绑定父任务调用 `complete_delivery` 时，原生宿主先做相同的完整映射检查；准备阶段的生产者自报清单不能跳过独立验收。全部 live 独立验收通过后，宿主从原始映射与真实审查回执生成交付清单，保留原有工具批准。批准等待结束时，安装适配器再次核对权限、来源、候选与独立证据，然后调用既有 `editor_delivery_finalize.py`；真实 main、CI、签发、Issue 关闭与启动入口回执仍由原交付器核对。

活跃生产检查要求原 Issue 仍 open。因此，映射中的业务与交付证据应能在原 Issue 最终关闭前被独立核实，例如已交付到 main 的精确候选；关闭原 Issue 是后续既有 finalizer 的实际动作。若原契约要求先关闭该 Issue 才能独立验收，该循环依赖尚不受此入口支持，不能把它改写成已通过。

若交付已发生但回执未知，原始请求保留为编辑器缓存内 `delivery-finalize-<pid>-<nonce>.request.json.original.json`。使用同一已安装宿主执行只读恢复（工作区必须是该请求的原 `source_root`）：

```sh
python tools/gonggong_bridge.py parent-delivery-readback --workspace /absolute/original/workspace --request /absolute/cache/delivery-finalize-….request.json.original.json --out /absolute/readback.json
```

此入口核对原账户、nonce、已有交付 journal/attempt、精确签发候选、main、CI 与原 Issue 契约；已撤销写权限但仍能读取的原操作者也可以回读。它不重新发布、不激活安装，也不从磁盘重建 live owner 或业务验收。已核实关闭而启动入口仍 pending 的回执继续使用既有原生 delivery-retry 路由；仅 readback 成功不等于恢复了新一轮生产授权。

实现边界：`parent_completion.py` 是既有 Godot 宿主工具的内部适配器，由已安装 `tools/gonggong_bridge.py` 的 `parent-completion`、`parent-delivery` 和显式只读 `parent-delivery-readback` 消费；生产动作由持有本轮 owner 的原生完成回调发起，JSON 文件不能建立 live owner。进程生命周期复用已安装 `tools/ainative/owned_process.py` 的 POSIX 进程组/Windows Job。回退恢复前一已验证编辑器及其配套宿主文件，保留原 Issue、工作树、执行/验收回执；不切换全局 hook、桌面调度或模型授权。
