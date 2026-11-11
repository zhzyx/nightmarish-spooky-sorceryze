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
