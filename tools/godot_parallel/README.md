# Godot 并行工单执行器

## 已验收成果接入当前项目

父会话可使用 `integrate_production_result`：先 `action=list` 取得实际 `producer_id`，再 `plan` 核对该生产项与当前打开项目的差异，`apply` 接入固定计划。该入口从存活宿主的独立验收取得候选，不能通过模型传入路径或普通 JSON 自行建立验收。当前项目可以位于同一 Git 仓库的其他工作副本；按实际打开项目解析目标，不把引擎开发工作副本误当游戏项目。

计划拒绝目标已有冲突、候选/终态变化和路径越界。执行遵循已有自动文件与自动命令授权，未开启时沿普通确认入口；未保存场景/脚本或项目仍运行时先保存/停止。完成后触发资源扫描，父会话沿已有导入、运行与日志工具继续验证，`applied` 只表示文件整合成功。

计划和原始字节备份保存在目标仓库根解析的 `data-collection/outbox/project-integration/`。`rollback` 核对当前权限、精确计划和目标字节；中断保留 journal，不猜测成功或覆盖后续用户修改。宿主保存回滚绑定，冷启动后仅允许明确恢复回滚，不由旧验收重新授权生产或 apply。项目迁移、回执损坏或未知目标变化须保留待核对状态。当前限制为单次最多 512 个变更文件、原始前后内容合计 64 MiB；大项目按独立工单逐批接入。

路径相对仓库根。编辑器设置 `ai_chat/parallel_work_orders_config` 指向宿主私有 JSON 的绝对路径，推荐保存在 `data-collection/parallel.local.json`。非空时“按工单落地”按配置启动独立 CLI 工作者（Codex 或其他支持标准输入的 CLI），每项独立 Git worktree。HTTP/CodeBuddy UI 执行器仍为串行；此通道不操作当前编辑器场景、菜单、构建或共享文件，不自动合入成果。

配置示例（占位符必须换成已验证的实际配置）：

python、codex 或 workerCommand.executable、worktree 和 registry 均使用绝对路径。共享预留根从真实 Git common directory 的父目录解析为 `data-collection/outbox`，因此从不同源工作副本启动也共用容量与资源锁。每次编辑器调用使用唯一批次请求和输出，回读绑定批次、需求和子项身份。

report.py 复用现有 Godot bridge.enqueue/flush，在模型启动前持久记录 handoff，完成/失败记录 step。上报身份是本执行宿主及 runner 摘要，不冒称司南 Agent。无法持久上报则阻止受影响模型启动；启动后的上报失败保持 reconcile_required。recorded_file 只表示本地谛听文件回执，不等于 Git 提交或消费。用量未知保持 null。

```json
{
  "nativeWorkspaceWrite": true,
  "authorityRef": "实际用户对独立工作副本原生执行的授权引用",
  "capacity": 2,
  "python": "C:/实际路径/python.exe",
  "codex": "C:/实际路径/codex.exe",
  "models": [
    {"id": "实际可用型号", "available": true, "targets": ["agent"], "capabilities": ["coding"], "preference": 1}
  ],
  "jobs": [
    {"order": 1, "worktree": "D:/实际独立工作副本1", "capabilities": ["coding"], "dependsOn": []},
    {"order": 2, "worktree": "D:/实际独立工作副本2", "capabilities": ["coding"], "dependsOn": []}
  ],
  "registry": "D:/实际司南登记表/registry.json"
}
```

使用其他生产 CLI 时，在同一配置中用 `workerCommand` 替换 `codex`。例如，已在本机安装并登录 CodeBuddy 的协作者，可用 Node 运行仓库固定版本的 CLI 入口，将以下成员加入配置，并将示例路径替换为本机绝对路径：

```json
"workerCommand": {
  "executable": "/opt/homebrew/bin/node",
  "args": [
    "/absolute/path/to/repo/tools/codebuddy_cli/node_modules/@tencent-ai/codebuddy-code/bin/codebuddy",
    "--print", "--output-format", "json", "--model", "{model}",
    "--tools", "Read,Glob,Grep,Edit,Write,Bash",
    "--allowedTools", "Read,Glob,Grep,Edit,Write",
    "--strict-mcp-config", "--mcp-config", "{\"mcpServers\":{}}",
    "--setting-sources", "", "--settings", "{\"disableAllHooks\":true,\"enabledPlugins\":{}}",
    "--no-session-persistence", "--permission-mode", "default"
  ]
}
```

`workerCommand.executable` 指向实际可执行文件；脚本可用相应解释器启动，如上例的 Node。示例允许文件读写；测试所需的 Bash 命令由本机 CLI 的权限策略决定。参数按数组逐项传递，每次启动用选定型号替换唯一独立参数 `{model}`，不经过 shell。宿主在独立工作副本根目录启动 CLI，经标准输入传入执行边界和工单提示。CLI 须支持非交互读取 stdin 并以退出码报告结果，权限和账户应在该安装实际验证；命令参数不要包含凭据。由同一组 `models` 登记该 CLI 实际可用的型号及能力。以同一批次、工单的 PID、日志、退出状态和 `workerBackend` 回读。替换配置后，原有已启动工单仍从其 ticket 回读。

目录必须来自实际宿主能力核验，型号不猜测。`nativeWorkspaceWrite` 是额外的原生 CLI 执行授权，不由 UI 的自动命令开关推导；UI 同时要求开启工具/自动文件/自动命令，禁止仅咨询。模型使用共用司南 selectModel，精确传入 CLI；回执 model 表示已请求型号，并非供应商侧实际路由证明。

`capacity` 是操作者按实际宿主资源、账号和授权配置的正安全整数，不再固定限制为两个槽位。每次事件只为就绪任务创建所需消费者；配置较大的容量不会提前创建空工作者。每个启动仍须取得共享容量槽和独立工作副本预留，未知工作者继续占用槽位。配置值并不是供应商可用额度或实际吞吐的测量结果。

工单依赖必须显式声明为原来源全局工单 ID；通过 registry 指向的现有司南 board 核验 acceptanceValid，不能以配置中的布尔值或型号能力自评替代验收。registry 必须绝对路径，其内部来源路径相对登记表目录。无依赖时可省略 registry。当前 board 适配已登记元衡来源，未接入的来源保持阻塞。不同工作副本必须属于同仓库，禁止主工作区和重复/嵌套工作副本。工作副本与每工单持久预留防止跨批次重复写入，共享容量槽防止多个编辑器超量。运行前逐项比较当前来源与工作副本的框架包指纹、执行真实 intake-only 与正式框架校验；候选未准入时拒绝启动，不能用测试门禁替代。

创建派发意图、进程运行与待验收分开。CLI exit=0 进入 review，不能自动关闭工单或合入。每批私有回执、日志与请求位于源工作区 `data-collection/outbox`；ticket/resource/capacity 预留统一位于真实 Git common directory 父级仓库根的 `data-collection/outbox`；保留失败和未知回执，不自动重派。编辑器退出会关闭 Windows 进程 Job；关闭一个子项通过文件事件请求取消其进程树，结果仍待对账。重启后不自动重跑。

新启动项在实际启动前写入独立 `registration`，并在真实进程终态写入 `terminal_receipt`；两者均返回绝对路径和原始字节 SHA-256。登记绑定宿主生成的 `execution_id`、实际工作副本与分支基线、Issue/需求/设计。终态附真实 PID、退出码、完整候选文件摘要、取消和上报状态。`transport_completed=true` 仅证明这次运输成功，`business_accepted` 保持 null。`jobs[].workerId` 可填写已授权台账中的实际 owner；省略时生成 `parallel:<execution_id>`，不能把它当模型会话 ID。独立审查必须核对原登记及终态当前性；重放保留原身份，登记或终态改变则进入 reconcile_required，不补造成功回执。

存活编辑器观察本次已启动执行器的实际结束事件，按原父会话、Issue、需求、设计和批次保存一份父通知。正常、失败和未知均保留真实状态；通知只要求父模型沿原授权核验回执及剩余验收，不能当作批准、依赖验收或合入。父会话停止、关闭或绑定变化不自动续办，切到无关会话不抢占；当前父会话的停止按钮向该批次工作者写入取消事件。设计变化、来源回执或通知落盘失败保持待核对/暂停，冷启动不自动重放。

模型缺失、已知未启动失败或依赖阻塞保留 waiting；修复模型目录或来源通过原 CLI 验收后，用户点“继续落地”是新的实际事件，按最新 board 只补位未启动工单。每工单预留保证已启动项只回读原回执不重派。未知结果或崩溃保留预留及容量占用，需授权宿主先核对原 PID/CLI 回执、工作副本差异和源工单，再归档私有预留；不能仅删除未知预留来重跑。不把所有子项完成作为父项验收。

测试 `node --test tests/editor/test_parallel_work_orders.mjs` 使用临时真实 Git worktree 和受控假 CLI、假门禁，验证 Codex 兼容路径及其他命令的实际子进程、参数/型号、标准输入、工作副本写入、门禁拒绝和去重，不能证明供应商调用、账户权限或生产准入。

Windows 的独立子进程树边界使用仓库锁文件固定的 Job Object 模块，即使选择 workerCommand 也需要该模块。可信 Windows 执行宿主可按 tools/codebuddy_cli/package-lock.json 在本仓库运行 `npm ci --prefix tools/codebuddy_cli` 准备依赖；通用工单核验入口不加载该模块。


宿主已绑定真实独立失败审查时，可在对应 request.workers 项传入 `repairOf: {execution_id, continuation_id, terminal_receipt:{path,sha256}, review:{path,sha256}}`。review 是完整失败 decision，包含原 candidate/audit_policy、生产 execution/worker/terminal、独立 reviewer/conversation/terminal、设计摘要以及逐项 `{id,met,evidence:[{path,sha256}]}`，至少一项 met=false；runner 核对原始字节、原票据、已知成功运输、实际候选和当前准入。这个私有数据接口不证明真实审查者身份，原生宿主必须沿实际完成上下文绑定，不能把任意 JSON 当批准。

每个前驱 execution 只有一个后继修复票据。原票据保持原字节；资源从匹配的原执行登记原子转交，启动前失败恢复原资源，已尝试启动而结果未知时保留占用。相同 continuation 重放仅回读；不同 continuation 不能争抢同一前驱，新的失败审查只能针对实际后继执行。修复的 ticket/registration/terminal 保存 repair_of，stdin 另附已核验的失败 reason/criteria 作为任务数据。修复完成仍进入 review，不能自己获得业务验收。

现有 Node 宿主直接加载 runner.mjs 与 repair.mjs；同一个 Node 可执行文件执行修复前后及失败回退测试。恢复旧 runner 时保留全部票据和审查证据；旧版本不能产生带 repair_of 的后继执行，原生消费者须拒绝缺少本次谱系的回执。未知、取消、过期来源均不可借此重新启动。
