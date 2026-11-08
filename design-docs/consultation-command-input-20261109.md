# 仅咨询会话的受信文字输入

request_id: consultation-command-input-20261109

真实工单：[#585](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/585)，type:bug；关联 #390、#393、#559。从 main dd4bdf8a 隔离，已真实 intake 并以实际非空职责接收本次夸父事件。

## 来源与边界

原用户要求验证引擎内聊天到交付全流程并修复阻断；本轮又明确要求已选中的会话自动通过命令输入。实际在已选中顶层空白会话、仅咨询、空草稿和空闲状态下，通用 HTTP `chat_send_message` 返回 permission_denied，消息未发送。原故障回执与调用意图由维护宿主保留，不能把该拒绝当成已发送。

修复仅扩展现有官方 Codex Desktop 受信 UDS 的普通文字 submit，使当前用户已经选择的顶层仅咨询会话走同一手动 `_send` 只读管线。生产发送继续要求原 owner、真实 Issue 和 snapshot。HTTP/editor 操作的仅咨询写入禁令不变，不模拟 GUI、不制造审批、不更改咨询或工具开关，也不增加模型工具权限。

仅咨询复选框冷启动默认关闭，因此 UDS 也支持显式单条 `consultation_only=true` 降权，不能传 false、数字或字符串。它不会临时勾选或保存全局模式；原零参 `_send` 保留，私有共同发送体从入口开始使用有效只读模式，并把它捕获到该消息。未提供字段的普通生产提交继续使用原守卫。该字段进入现有路由幂等摘要，相同 request_id 不能删除或更改只读意图。

保留内核 peer/固定官方签名身份、fresh exact context（含 PID/host_instance）、请求幂等及反重放、IME/草稿/附件/队列/历史/忙与自动执行 opt-in 等现有边界。模式切换或上下文变化后拒绝旧请求，不能将咨询委托变成生产委托。

## 单元与验收

这是同一入口资格判断与提交动作的不可分割小修复，保留单 Issue。

1. 私有 `_sc_` 原生宿主中，由真实官方 Desktop peer 发起：顶层仅咨询、无 owner/Issue/snapshot、空草稿、空闲的文字提交得到真实只读模型回答。
2. 不改 consultation/tools/auto 开关，不丢草稿；忙、子会话、模式变化、旧 PID/实例、草稿/附件、队列及重复冲突有原生实测。IME、历史恢复及其余未改变的恢复守卫保留并静态核对；不冒称在无头环境验证硬件输入法。
3. 关闭本地工具时纯文字可发送；恶意工具请求触发原管线拒绝并停止。开启本地工具时保留既有有界读取，写文件、命令、构建、重启、派生验收、完成交付及编辑器配置操作全部拒绝。普通 HTTP/editor 写仍拒绝。生产无绑定路径仍拒绝，既有已绑定生产路径不回归。正常手动发送所需的聊天/快照和连接选择保存仍按既有管线执行，不声称零持久写。
4. 固定编译与必要静态检查、真实同产物 typed/UDS 回归、独立安全审查、正式 gate/writer 与精确 CI。按协调保留 main 合入等待；最终应用由维护宿主另行构建验收，不替换正在使用的应用。

## 执行责任

本单唯一实现与源发布主责为当前 `/root/runtime_entry_fix`。人类授权来自原完整流程请求及本轮明确命令输入要求；Root 负责生产应用验收与合入协调。实现和测试均在从最新 main 创建的独立工作副本，不触碰冻结候选、用户桌面、原项目历史或全局配置。验证报告如使用合成模型，须与真实 provider/生产验收区分。

## 命令用法与当前验证

在官方 Desktop 进程链直接使用系统 `/usr/bin/python3`，显式指定实际已观察的引擎 PID 和用户选择的项目：

```text
/usr/bin/python3 tools/editor_instruction_client.py --project /path/to/project --instance PID context --consultation-only --wait 10
/usr/bin/python3 tools/editor_instruction_client.py --project /path/to/project --instance PID submit --consultation-only --text-file message.txt --expected fresh-context.json --request-id UNIQUE_ID
```

先保存该次真实 context 的完整结果为 fresh-context.json。只读可用性由 consultation_instruction_available / consultation_blocked_reason 表示；instruction_available 仍描述普通提交。accepted / instruction_submitted 仅表示消息已进入正常聊天，不表示模型或业务已完成。该入口仍要求自动执行 opt-in、当前顶层父空闲、队列为空且未暂停、空草稿及其余现有保护。

作者同产物 macOS 原生无头验证：47 项仅咨询 UDS/CLI 检查、37 项既有生产 UDS 回归均通过，真实内核 peer 验证通过；模型/远端 Issue 为本地离线夹具，不代表已运行用户生产账号或真实 provider。新增只读输入套件保留了先前夹具失败原件：未选中的初始 ctor 槽缺 conversation、关闭工具后恶意调用按原政策停止而非继续模型、普通 HTTP 原权限守卫先行拒绝。夹具按实际合同修正后通过，不追认失败轮次。
