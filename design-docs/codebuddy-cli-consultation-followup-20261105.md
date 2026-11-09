<!-- gonggong-request:codebuddy-cli-consultation-followup-20261105 -->

# CodeBuddy CLI 仅咨询与权限边界

关联 #83；来源为 #46 的用户授权后续。原验收覆盖连续代码读取、只读编辑器状态、禁止写入和真实 shell、不可在会话中升级权限、取消/关闭/恢复与工单隔离；未具备边界时拒绝执行。Windows 原始范围与真实供应商结果分别记录。

## 2026-11-09 当前实现回读

原单仍记录的“CodeBuddy 不支持仅咨询”已被后续 #559 / PR #571 交付取代。实现提交 `40b89ac3b0dc5cf29f85457ef1a6a4501ac27219` 已进入 main。`AIChatSubAgents::supports_read_only_backend` 与 `_start_message` 使用宿主强制的只读模式；ACP 只启用受宿主中介的 Read 与保留的只读 Bash facade，禁用原生 Glob/Grep，不启动真实 shell。文件写入、终端、权限回调和同进程 capability tuple 再次检查权限，不依靠提示词。

锁文件固定 CodeBuddy 2.176.0、ACP SDK 1.9.0。当前 `test_codebuddy_acp.js` 包含强制写入/真实shell拒绝、同进程模式升级拒绝、连续 list_scripts/list_directory/read_script 回传。既有 #559 的 65 项协议验证与独立审查位于 `data-collection/requests/editor-command-gaps-batch-20261108/codebuddy-protocol-validation.json` 和 `final-independent-review.json`；其 mock ACP、原生几何与真实供应商边界保持原样。当前协议源码相对历史输入的变动需要定向复验，不能把旧65项记成本次执行。

本轮用户要求收敛 macOS/Windows 模拟环境。此允许离线宿主边界补验，不使 mock CLI 成为真实 CodeBuddy 供应商，也不建立独立 OS 沙箱。生产账户调用、真实固定版本CLI越权实测未执行时仍留未知；代码实现与模拟验收分别写回 #83。

官方权限说明供版本核对：[权限模式](https://www.codebuddy.cn/docs/cli/permission-modes)、[权限规则](https://www.codebuddy.cn/docs/cli/permissions)。不能将 plan 模式单独视作完整只读隔离，实际边界取自本仓库宿主回调与每轮权限固定。

本轮统一证据：`data-collection/before300-20261109/validation.json`（路径相对仓库根）。

本次实际复验：固定并校验 ACP SDK 1.9.0 / zod 4.6.7 后，三项当前只读边界测试全部通过（写入/真实shell/同进程升级拒绝、生产父项只读审查请求、连续类型化读取）。同时运行完整65项得到63通过、2项因没有安装固定CLI的 Edit/Glob 实现源码而无法执行；不声明全套通过。只读相关检查没有依赖该缺失文件，不将供应商运行写成已验证。
