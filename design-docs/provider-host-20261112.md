# 外部编辑器指令的受信宿主解耦

父需求：provider-independence-20261112。用户于 2026-11-12 明确要求执行并修复全部已审计 Codex 强依赖，授权当前会话持续交付。

范围：macOS 外部指令入口从固定 Codex 身份扩展为当前用户明确登记的受信宿主；保留进程签名、同用户、完整祖先链、抗 PID/身份变化、请求上下文与操作权限核验。不得通过任意签名或任意同用户进程放行实现解耦。提供明确注册/撤销入口，Codex 兼容。写入责任 ai_chat_external_peer.*、专用宿主配置工具/测试、必要外部指令客户端及本设计；不改通用模型设置。不在 Windows 宣称 macOS 实测通过；平台 CI、身份拒绝及代表接入是验收项。原生 Codex 子 Agent 仍保留专用协议，不把通用进程冒充原生工具。独立审查与 main 回读后按实际验收关闭。


## 实现与宿主接口

原生边界：`editor/docks/ai_chat_external_peer.cpp/.h` 仍由编辑器原生构建消费，新增 `REGISTERED_HOST` / `REGISTERED_HELPER` 身份。完整链仍必须到真实 PPID 1，每个进程必须同用户、代码受信、两次出生时间及签名摘要一致，链上 Godot 始终拒绝。只有明确登记的 host 或兼容 Codex desktop 可以提供宿主锚；helper 不能提供该锚。请求上下文、授权与新鲜度由原有上层验证继续处理。

宿主工具边界：`tools/editor_trusted_hosts.py` 为独立 Python CLI，不嵌入编辑器。以系统账号数据库 `getpwuid(getuid()).pw_dir` 为解析基准，在 `.gonggong-external-hosts/hosts-v1.tsv` 存储本机名单，不使用项目目录、HOME 环境变量或网络配置。目录 owner-only，文件 owner-only 且单硬链接，均禁止符号链接。名单每行是 `role<TAB>TeamID<TAB>identifier<TAB>CDHash`；上限 32 KiB。固定 v1 文件名是接口版本；未知格式拒绝。登记使用独立锁与同目录原子替换。

名单显式绑定 role、开发团队、签名标识、40 位 CDHash。运行进程仍必须通过 Security.framework 的完整有效签名核验与 `anchor apple generic`、精确 identifier、证书 Team ID、精确 CDHash requirement，任意签名、ad-hoc、自签名、同 UID 均不自动受信。代码升级须重新登记。名单在每次 verify 前后回读，内容变化拒绝当前校验；撤销在下一次校验生效，不要求重启引擎。既有 Apple 平台辅助进程及官方 Codex desktop/CLI 兼容规则保留；本工具的 revoke 只撤销显式登记项，不是禁用内建 Codex 的开关。相同 UID 的主动攻击者可改写本用户名单，此机制不声称隔离同账户内已完全失陷的进程。

macOS 用户先查看真实身份，再显式登记（下列占位值必须换成 inspect 实际输出，不可照抄）：

```sh
python3 tools/editor_trusted_hosts.py inspect /Applications/Host.app --role host
python3 tools/editor_trusted_hosts.py register /Applications/Host.app --role host --team TEAMID1234 --identifier com.example.host --cdhash ACTUAL_40_HEX_CDHASH
python3 tools/editor_trusted_hosts.py list
python3 tools/editor_trusted_hosts.py revoke --role host --team TEAMID1234 --identifier com.example.host --cdhash ACTUAL_40_HEX_CDHASH
```

每个非 Apple 的辅助进程必须单独用 `--role helper` 登记。工具在 register 时核验实际签名与提供的预期值完全一致；inspect 本身不授予权限。以 `/usr/bin/python3 tools/editor_instruction_client.py` 从该宿主真实后代链执行原有客户端。回退为撤销新增登记，或恢复先前精确名单；原生代码回退使用原提交。操作权限不由登记授予。

## 验证与未完成平台证据

2026-11-12 Windows：`py -X utf8 -m unittest discover -s tools -p test_editor_trusted_hosts.py -v` 运行 10 项，8 项通过、2 项 macOS 实测明确跳过。通过项覆盖精确增删及恢复、格式/注入拒绝、错误属主/权限/硬链接、完整 requirement、模拟签名失败及预期身份变化不写入、非 macOS 拒绝。模拟 subprocess 不代表 Security.framework 或真实签名通过。

`tests/editor/test_ai_chat_external_peer.cpp` 新增注册 host/helper 完整链、helper 无锚权限、未知中间进程、跨 UID、截断链、代码变化、撤销分类与 PID 重用拒绝测试；这些是纯链验证，原生编译及执行回执由集成责任者另行记录。已有 macOS Unix peer 实测继续验证编辑器自己的后代不得借用宿主祖先授权。

真实 macOS 自动化入口：`python3 -m unittest discover -s tools -p test_editor_trusted_hosts.py -v`。MacOSIntegration 使用真实 `/usr/bin/codesign` 创建 ad-hoc 与去签名副本并断言拒绝，使用实际 POSIX 文件执行原子写入、回读、撤销、权限及符号链接拒绝，不使用 mock。仍需 macOS native CI 编译、原生测试实际回执，以及至少一个可用第三方开发团队签名宿主/辅助程序的成功请求、未登记拒绝、升级摘要拒绝、撤销后拒绝和原有 Codex 兼容实测。当前 Windows 结果不能满足这些验收项，未取得回执前不得称整体验收完成。

实际写域为原生实现与头、`tools/editor_instruction_client.py`、新增宿主工具及其测试、现有 `tests/editor/test_ai_chat_external_peer.cpp`（初始 .h 路径经派发责任者纠正）、本设计。复用了 godot-build-placement/trace-native-consumer revision 11：按真实消费者区分 native 与 host_tool，且单平台证据不外推到 macOS。

独立审查纠偏：相同 Team ID/identifier/CDHash 的 helper 与 host 双项曾可能因排序优先匹配 helper。现 register 对相同精确签名身份替换旧角色，revoke 仍按含角色的完整项精确撤销；原生读取已有双项时显式 host 优先。新增升级、降级、撤销不误删另一角色与旧双项清理回归。Windows 10 项中 8 通过、2 个 macOS 实测跳过；ruff 0.17.1 format/check 和 clang-format 22.1.5 检查通过，原生生产输入已交给集成责任者构建。

补充真实进程链入口 `tools/run_macos_external_host_acceptance.py`，属于仅在一次性 macOS GitHub runner 执行的宿主验收工具，不嵌入引擎。输入为当前候选编辑器、官方发布且固定 SHA-256 的 PowerShell 7.6.9/7.7.0 包，以及可选官方 Codex 应用；输出实际签名、进程 PID、原生 socket 鉴权回执和逐项结果。通过用户域 launchctl 后台启动完整祖先链，不修改签名、不打开可见桌面、不调用模型，登记前要求现有信任条目为空，结束撤销测试条目并清理自有进程。

workflow 在编译前执行真实签名/launchd 预检，编译后验证未登记拒绝、登记成功、角色升降级、错误摘要拒绝、同供应商且经产品版本回读确认的真实升级先拒绝再登记成功、撤销拒绝。Codex 仅在官方 Electron RunAsNode fuse 已允许时验证内建签名锚；缺条件记 unavailable，已具备条件后请求失败仍判失败。报告分别保留 non_codex_host_ok 与 full_signed_anchor_acceptance_ok，不把前者冒充后者。脚本失败可回退至已有纯链测试入口，但不能由此宣称真实链通过；所有实际结果以 CI 上传回执为准。

首次真实 macOS run 43111713606 的 arm64 编译成功，随后 Python 签名拒绝用例在复制 `/usr/bin/true` 时因 `shutil.copy2` 继承系统受保护文件标志而失败，原生测试尚未执行。夹具改为只复制二进制内容并设置 owner 执行权限；实际 codesign/ad-hoc/无签名拒绝断言保留，平台 Python 测试移到编译前。故障按真实运行关联 #856，并关联原工单 #843 与父 #840；Windows 的跳过不能证明此 macOS 故障恢复。

后续 run 43118045814 的真实签名拒绝与存储测试已通过，宿主预检停在官方双版本 PowerShell 的严格签名校验。排查发现登记工具把裸 requirement 文本传给 `codesign -R`，而 Apple 命令将无 `=` 前缀的值作为文件名。已仅在 CLI 参数加 `=`，保留完整 Team ID/identifier/CDHash/Apple generic 表达式；原生 `SecRequirementCreateWithString` 仍使用原始 DSL。新增分阶段签名回执与实际 macOS 字面表达式解析测试。旧运行没有阶段诊断，不能据此断言全部失败由该语法问题引起；仍须复验完整宿主链。此修复是独立宿主工具变化，不改变前次已构建的原生输入。

命令语义依据 [Apple Code Signing Tasks](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/Procedures/Procedures.html) 与 codesign 手册：文本 requirement 需字面前缀；通用程序各架构分别签名。登记时保留全部架构完整性核验，按实际观察到的 Team ID/identifier/CDHash 找到唯一对应架构，仅对该架构执行精确摘要要求；不依赖 Python 的 Rosetta 架构猜测，也不把其他架构自动加入信任登记。

实际 run 43120417239 已通过 14 项 macOS/通用登记工具测试（另 1 项非 macOS 拒绝用例跳过）及 6 项验收门禁测试，两个固定官方 PowerShell 包的严格签名检查均通过；剩余失败是验收工具错误要求不同版本维持同一 Identifier。真实 PowerShell 7.6.9/7.7.0 的标识带各自构建 UUID，会随版本改变。升级夹具现以官方固定包摘要、实际 `pwsh --version` 产品/版本回读、同 Team 和不同 CDHash 确认升级，并记录 identifier_changed；生产登记仍精确绑定新标识及摘要，同标识仅改摘要的拒绝用例保留。此调整是对真实供应商升级方式的验收纠偏，不放宽鉴权。

实际macOS run43123215252及43125700093均已完成原生编译、ExternalPeer原生测试及8个真实签名PowerShell请求场景（未登记拒绝、显式登记、角色升降、错误摘要、实际版本升级前后、撤销）。最新回执绑定签发c42411ce，不能外推其他候选的完整Mac流水线。官方Codex应用的Team/id/摘要严格核验成功，但当前唯一应用ChatGPT.app无预期Electron Framework路径，因此无实际Codex后代socket请求，full_signed_anchor_acceptance_ok=false。#843继续保留此项，恢复条件是在授权macOS Codex原生会话中，用相同候选私有headless编辑器取得真实context请求回执；不将终端、任意同UID进程或WindowsCLI生成替代该祖先链。额外Windows归档工具MSI提取被宿主策略拒绝，内建tar不能读DMG；未安装软件、未绕过策略。

实现已随 PR #872 合入 main `e15a49f9b7dbbdbb1b585fc2b68cc3f252d88c8b`。文件复制保护标志故障 #856 与 codesign 命令预检故障 #859 均按真实 macOS 同步骤恢复及主线回读关闭；这不表示 #843 整体验收完成。当前根会话继续协调剩余桌面链，#843/#850/父#840保持开放，无其他执行者接受交接。具体最终运行与状态以 `data-collection/provider-independence-840-delivery.json` 及关联 Issue 时间线为准。

最终 run43131315713 绑定 PR872 精确签发41a47090，全部步骤成功；真实 macOS 编辑器摘要 `a739a5a9eeff5cb7d48316a8f23e41b8e7e7aefdaa5cd9e3f557b02f2cb3896e`。8个真实签名场景全部 passed，完整模型发现和取消回归成功。官方 Codex 应用仍缺测试工具预期的 Electron 子进程入口，codex.state=unavailable、full_signed_anchor_acceptance_ok=false；整轮CI成功只证明其声明的可执行范围，不将缺失桌面链补记通过。
