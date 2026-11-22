# #1709 Windows 工作进程退出基线

从主线提交 `9793b67af36f371e151a69cf7fe4a9d98fbbfdca` 的 `tools/godot_parallel/runner.mjs` 启动本地夹具。实测环境为 Windows 11 x64 build 26200、Node 24.22.1、Python 3.12.14。启动时运行生产 CLI 的真实 Issue intake、框架校验、登记和本地谛听上报。每例创建单独的项目仓库、工作树、容量与任务预留。对照为探针单独启动的外部父子进程，两者不申请 runner 槽位。

在 R06 主线 `2ee48917eb54b82a14c381ffc8cb3c290b49bd14` 上独立复跑两例，生产 runner 与 Win32 依赖的摘要均与上轮一致。

| 已触发动作 | 退出后目标工作者及孙进程 | 对照树 | 产品回执与占用 |
| --- | --- | --- | --- |
| 写入该工作者的 `.cancel` | 原进程句柄均已置为退出 | 两个原句柄存活，子进程回写动作后才生成的随机挑战 | `cancel_requested=true`、`reconcile_required`、`transport_completed=false`，容量与资源锁各保留 1 个 |
| 在两棵树就绪后仅终止 runner | 原进程句柄均已置为退出 | 两个原句柄存活，子进程回写动作后才生成的随机挑战 | 结果仍为 `running`，无终态回执，`.running` 标记及两类锁保留 |

`plan1-windows-runner-baseline-1709.json` 保存整合工作树复跑的完整观察。字段包含产品登记与终态摘要、目标与对照运行号、PID、父 PID、原始 Windows 句柄值和创建时间、动作前后状态、占用文件摘要及对照应答。句柄值仅在记录它的 Python 进程内有效。两例的容量和资源锁在动作前后字节相同。首轮独立运行的回执另存在本次工作树的 `data-collection/receipts/1709-windows-first-pass/first-pass.json`，SHA-256 为 `bc87b3b996cb0d37c4ea8ac7af494679da9b085ea6ddf5e7b1a5d672496cf0aa`。

`WaitForSingleObject` 的已退出结果证明对应进程实例终止。产品写出的 `reconcile_required` 表示该执行需要核对，取消后的业务验收值为 `null`。受测层是独立 runner；编辑器正常关闭、R02 交接后归还占用以及其他操作系统尚待相应入口实测。

## 复跑

在一次性 Windows x64 工作树根运行 PowerShell。Node、Git 及能回读 #1709 的 gh 须可用。生产入口从其安装目录解析 Job Object 原生模块；已按 `tools/codebuddy_cli/package-lock.json` 安装依赖时可直接运行下方探针。若环境提供 npm，可在这份一次性工作树中执行 `npm ci --prefix tools/codebuddy_cli --ignore-scripts --no-audit --no-fund`。本次机器没有 npm，实际使用以下 PowerShell 7 命令核对原包并仅提取测试所需模块。测试使用独立的本地 Git 仓库；GitHub 仅用于回读原工单。

```powershell
$ErrorActionPreference = 'Stop'
$packageLock = Get-Content -Raw tools/codebuddy_cli/package-lock.json | ConvertFrom-Json -AsHashtable
$locked = $packageLock.packages.'node_modules/@tencent-ai/codebuddy-code'
$stage = New-Item -ItemType Directory -Path (Join-Path $env:TEMP ([guid]::NewGuid()))
$archive = Join-Path $stage.FullName 'package.tgz'
curl.exe --fail --silent --show-error --max-time 120 -o $archive $locked.resolved
if ($LASTEXITCODE -ne 0) { throw 'npm package download failed' }
$hash = [Convert]::ToBase64String([Convert]::FromHexString((Get-FileHash $archive -Algorithm SHA512).Hash))
if ("sha512-$hash" -cne $locked.integrity) { throw 'Package integrity mismatch' }
tar.exe -xzf $archive -C $stage.FullName package/bin/native/win32-x64/job-object.node
if ($LASTEXITCODE -ne 0) { throw 'Locked native module unavailable' }
$dest = 'tools/codebuddy_cli/node_modules/@tencent-ai/codebuddy-code/bin/native/win32-x64'
New-Item -ItemType Directory -Force $dest | Out-Null
$module = Join-Path $dest 'job-object.node'
if (Test-Path -LiteralPath $module) { throw 'Target exists; check the installed module' }
Copy-Item -LiteralPath (Join-Path $stage.FullName 'package/bin/native/win32-x64/job-object.node') -Destination $module
```

复跑时选用新的 JSON 回执路径。命令从仓库 Python 探测入口取得可执行文件。探针自行清理各试验临时项目及控制进程。进程退出与对照应答均满足时退出码为零；锁与票据留存情况见 JSON。

```powershell
$probePython = (& ./tools/run_issue_gate.ps1 -ProbeOnly | ConvertFrom-Json).python
$receipt = Join-Path $env:TEMP ("windows-runner-" + [guid]::NewGuid() + ".json")
& $probePython -X utf8 tests/editor/probe_windows_runner_cleanup.py --receipt $receipt
if ($LASTEXITCODE -ne 0) { throw 'Windows runner probe failed' }
Get-Content -Raw $receipt
```
