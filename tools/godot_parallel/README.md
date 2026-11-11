# Godot 并行工单执行器

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

模型缺失、已知未启动失败或依赖阻塞保留 waiting；修复模型目录或来源通过原 CLI 验收后，用户点“继续落地”是新的实际事件，按最新 board 只补位未启动工单。每工单预留保证已启动项只回读原回执不重派。未知结果或崩溃保留预留及容量占用，需授权宿主先核对原 PID/CLI 回执、工作副本差异和源工单，再归档私有预留；不能仅删除未知预留来重跑。不把所有子项完成作为父项验收。

测试 `node --test tests/editor/test_parallel_work_orders.mjs` 使用临时真实 Git worktree 和受控假 CLI、假门禁，验证 Codex 兼容路径及其他命令的实际子进程、参数/型号、标准输入、工作副本写入、门禁拒绝和去重，不能证明供应商调用、账户权限或生产准入。

Windows 的独立子进程树边界使用仓库锁文件固定的 Job Object 模块，即使选择 workerCommand 也需要该模块。可信 Windows 执行宿主可按 tools/codebuddy_cli/package-lock.json 在本仓库运行 `npm ci --prefix tools/codebuddy_cli` 准备依赖；通用工单核验入口不加载该模块。
