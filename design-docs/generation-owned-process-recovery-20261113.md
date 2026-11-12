# 生成适配器自有进程回收与动作任务恢复

<!-- gonggong-request:generation-owned-process-recovery-20261113 -->

## 来源、责任和范围

- Issue：#1003，父需求 #978；来源主线 `308bc83c19ae7cd1811496cca0e7062e6b30dab0`。
- 用户授权：`codex-user-ai-github-integration-refactor-20261112`。本候选实现责任为原生工作者 `/root/sinan_6d39b3ab904e5da2`；根责任者负责独立审查、整合、阎罗交付与工单验收。
- 原审计复现了三个 `_run_owned` 只终止直接进程、子进程仍活动，以及 macOS `motion_jobs.process_identity()` 读取不存在的 `/proc`。
- 本次仅修改宿主 Python 生成适配器、动作恢复及回归。冻结框架、真实模型、凭据、编辑器工作台 #971 和 #997 的 `tools/editor_provenance_process.py` 均不修改。

所有本文路径以仓库根解析；私有日志与依赖另按验证回执中给出的相对路径解析。

## 实现和边界

三个适配器使用 `tools/ainative/owned_process.py`。命令 stdout/stderr 经管道持续排空并按调用方原上限截断写入；超过上限即记录失败，即使短命写入者在轮询之间已经退出也不能返回成功。超时、取消、回调异常、非零退出和正常结束均回收该调用持有的本地进程边界。

POSIX 使用新会话的独立进程组；`waitid(WNOWAIT)` 观察直接子进程而不提前回收组长，防止 PGID 被复用。只向本次实际创建且仍由句柄保留的组发送信号，不接管磁盘 PID。Darwin 对只有僵尸成员的组可能返回 EPERM，此时仅在固定系统 `/bin/ps` 的数值组成员和状态快照确认全部为 Z 且包含被保留组长时，接受无活动进程；查询失败或活动成员仍报错。可信命令不得通过 setsid/setpgid 主动脱离会话；本实现不是恶意代码沙箱，也不在进程被外部 SIGKILL 后接管丢失的本地拥有者。

Windows 复用已提交宿主 `tools/editor_provenance_process.py` 的 WinAPI：创建不可继承、关闭即杀的 Job，先以 `CREATE_SUSPENDED | CREATE_NO_WINDOW` 创建命令，分配成功后才恢复线程。分配失败不恢复线程。清理后查询 Job 活动成员。该文件作为已有宿主依赖使用，本单没有修改它。Windows 真实内核执行未在本 macOS 宿主冒称通过；契约桩验证分配顺序和分配失败，真实进程用例保留给 Windows 宿主执行。

Kimi 的启动器会退出并留下生成子进程；图像 `_cli`、网格 `_cli` 和纹理 `_adjust` 持有一个完整调用作用域，在 watcher 运行、结果解析结束或异常退出后统一回收启动树。上传等普通命令完成后立即回收。清理本地进程不等于取消远端任务；原任务意图、未知远端回执和禁止自动重发规则保持有效。公共建模和雕刻指纹同时包含新增生命周期实现，Windows 指纹还包含其实际 Job 实现依赖。

动作任务在 Darwin 读取 `libproc` 的真实创建时间（秒和微秒）并核对返回 PID；Linux 正确解析包含空格和括号的 comm 字段；Windows 保留创建 FILETIME。恢复查询区分 running、dead 和 unknown：无法获得创建身份但 PID 仍存在时保留 reconciliation_required，不写入虚假的失败终态，不自动重发。已经确认消失或 PID 已被新创建身份复用时才能判定原进程终止。

这是独立运行的宿主 Python 工具模块，输入为既有可信 CLI 参数和输出流；宿主接口为三个现有 `_run_owned` 方法，回退为同一候选的整体源文件回退。独立审查后增加 `editor/SCsub` 与 `editor/ainative/builders.py` 的嵌入依赖闭包修复：Job helper 是显式 SCons 输入，进入生成头文件和包内容摘要，改动要求重新生成嵌入包并重建编辑器；现有已安装二进制不会自动获得该变更。本次执行源选择、生成头文件和离线解包消费测试，没有原生二进制安装/更新/回退验收，不启动 Godot GUI，也不将合成工件当作模型推理验收。

## 验证和交接

详细回执：`data-collection/generation-owned-process-recovery-1003-validation.json`。

- 三个真实适配器 × 七种实际进程用例（正常、错误、超时、取消、持续输出洪泛、快速退出洪泛、活动回调异常），验证子孙进程不再活动、无关进程继续运行、输出文件不超过限额。
- 两个 Kimi 适配器 × 六种启动/等待/解析终态，以及 POSIX 组长保持未回收、Darwin 短命命令僵尸组长回收。
- 动作任务实际 OS 创建身份、实际子进程活动/退出恢复、PID 复用拒绝、无法核实身份保留未知、同键单次启动及不可变终态。
- 相关生成、Kimi、建模、雕刻、loopback API planner 和动作合成回归，共 141 项，111 执行通过、30 原平台/原生依赖跳过。Ruff 十一个修改文件检查和格式检查；mypy 八个修改实现文件。
- 所有模型任务均使用合成 CLI 或 loopback；无付费模型调用、真实推理、外部凭据读取或安装版替换。

必要独立审查、正式门禁、精确候选 CI、main 回读和关闭工单由根责任链继续；本地通过不声明已交付 main，也不验收父 #978 的其他范围。


## 独立审查 R1/R2 修正

初次候选独立审查为 changes_required，不能作为已准入交付。审查者 `/root/sinan_842f663439fe6bd0` 使用源字节和确定性脚本复现了以下缺口，修正仍归原实现责任者，复核沿原审查链进行。

- R1：旧代码只支持仓库 `tools/ainative` 布局，真实嵌入包将 Python 平铺到 `tools`，又未包含 Job helper。现在打包器统一计算 `bundle_sources`，SCsub 显式登记完整依赖，现有离线包检查也复用同一闭包；SCons Node 使用绝对源路径，避免活动 SCsub 目录影响。运行时指纹与模块加载共用 `_windows_helper_path`，分别支持仓库和内嵌布局。实际 SCsub 源选择/构建动作回归验证生成头文件包含 helper、离线内嵌文件能加载、源摘要随 helper 改变，以及缺失依赖拒绝执行。未修改 #997 的共享实现。
- R2：旧代码将直接启动器退出误当作启动日志已完成写入。现在线程和返回前的观察者共用短临界区进行非阻塞管道抽取与写盘；直接进程退出后，主线程主动排空已到达数据并等待临界区内已有数据写入，再交付成功返回。该屏障不要求继承管道的子进程关闭、不采用固定睡眠、不提前杀树。Windows 使用 PeekNamedPipe（未知错误不当作 EOF），POSIX 使用 select/FIONREAD。回归人为延迟实际日志线程，验证返回时两条启动标记完整可读、实际后代继续存活至 watcher 完成，然后由同一作用域回收。

复核事件 `ed44fe65effe69e711217ef473b8448d944461237b8b8515dc5407116b8fe513` 已按夸父 detect/receive/assess 关联原 bug #1003，不新建重复工单。最终候选需要原独立审查者重查；Windows 真机和重建后的内嵌二进制验收仍不能由本机合成检查代替。
