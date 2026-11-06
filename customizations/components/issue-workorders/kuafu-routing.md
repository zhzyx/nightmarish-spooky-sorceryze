# 夸父阻塞接单、上报和复验

路径均相对仓库根。有效角色取自 CURRENT_FRAMEWORK.json 指向的框架。按 agents/kuafu/AGENT.md 与 skills/kuafu/SKILL.md 处理真实阻塞。用户报告、本地故障、GitHub 事件和独立宿主均可作为来源。

## 活跃宿主的操作

1. 绑定真实 Issue 和稳定需求 ID，保留失败动作、候选、来源修订、原始诊断和已有 bug 链接。去重，缺少 bug 时在同一事件建单，并在 bug 或原工单正文记录关联。原故障发生在其他人的任务中时先明确原发布者和唯一修复责任。准备、排队、发送、接单和实际结果分开记录。
2. Windows 用 tools/run_issue_gate.ps1 -ProbeOnly 获取可用 Python。以下命令中的 python 指经验证的 Python 3.11+，在可信安装运行。--repo 指向实际检测工作树。提交门禁和协作者提交 CLI 会在失败时给出 incident；仓库和 Codex 派发入口按实际绑定工单转送失败。对用户报告、依赖异常、工具缺失、引擎或其他未自动接入的入口，当前宿主立即调用 detect。若 Git 或 Python 也无法启动，应从可用宿主在真实 bug 中登记此次失败，待恢复时核对；不丢弃原证据。
3. detect 尝试向 main 上的夸父 GitHub 工作流提交最小信号，并保留本地记录。dispatch_requested 表示触发请求得到返回；核对该工作流的报告、bug 及原单通知。该工作流从可信代码执行有明确范围的规则初判。需要技术排查时，当前活跃宿主无需等待远端初判，使用 receive 读取已准入角色上下文，结合原日志核对故障，用 assess 记录根因、责任与下一步。权限不足、未配置的旧 main、回执不明或离线时保留 pending，不能计为已接收。明确本地/测试范围可设置 GONGGONG_KUAFU_LOCAL_ONLY=1 阻止远端触发。
4. 同一台设备的私有记录在 Git common-dir 下的 gonggong-kuafu/；记录包含本机工作树和摘要，禁止发布整个目录。--worker 为宿主声明的工作者引用；GitHub 登录回读验证操作者，独立 Agent 启动另附真实工具回执。--authority 填写本次可核实的授权引用。assess 调用谛听文件接入，并将判断写入原 Issue 后回读。注意公开字段只放可公开的证据和摘要；不包含 Token、原始命令输出或私人聊天。
5. 优先修复当前权限范围内的故障，或通知能处理该步骤的唯一责任者。合入源头修复后，按原操作、候选和失败作业定向复验。相同工作树成功重跑原门禁/发布阶段可生成私有重验回执；新候选的结果单独核对。实际消费者核验前保留未知。原发布者接收及其候选 CI 通过后才能报告交付恢复；业务 Issue 按其验收独立关闭。

以下为命令形状，实际调用时替换参数；同一故障复用 incident。未知根因在诊断中写明待核实项。

```text
python customizations/components/issue-workorders/kuafu_incident.py detect --issue NUMBER --request-id ID --action user-report --evidence SOURCE_REF
python customizations/components/issue-workorders/kuafu_incident.py receive INCIDENT --bug BUG --worker WORKER --authority AUTHORITY
python customizations/components/issue-workorders/kuafu_incident.py assess INCIDENT --bug BUG --worker WORKER --authority AUTHORITY --evidence SOURCE_REF --diagnosis FINDING --next-action NEXT
python customizations/components/issue-workorders/kuafu_incident.py status INCIDENT
python customizations/components/issue-workorders/kuafu_incident.py forward INCIDENT
```

远端恢复后，从原检测工作树运行 forward。已有发送意图但回执丢失时，此命令先按实际操作者和 incident 查找运行，查不到则保留待核对状态。

## GitHub 事件

.github/workflows/kuafu-blockers.yml 从默认分支校验真实运行、作业和原工单。失败运行、明确被标为 blocked 的工单和认证宿主提交的本地阻塞信号进入初判。一次回执只能说明它覆盖的动作；零作业启动失败保留作业证据为空。成功事件须绑定先前事故和实际覆盖的作业后才能作为恢复证据。运行报告标明宿主、来源、角色上下文和已知范围。暂存的文件回执、工件留存和实际消费分别核对。该入口由事件触发。
