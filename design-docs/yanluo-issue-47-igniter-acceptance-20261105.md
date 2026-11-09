<!-- gonggong-request:yanluo-issue-47-igniter-acceptance-20261105 -->

# 完成原生点火器跨重启、安装契约与跨平台剩余验收

## 当前推进（2026-11-09，Windows CI 验证待回执）

用户本轮要求收敛为mac/Windows模拟验收，不等待Linux或旧x86/Clang环境。PR638/641已进入main；#56/#83/#93/#94/#95/#158/#160的完成状态已逐单回读，#49/#51/#92保留原症状/物理交互未知。

本机缺少PowerShell且三种下载均未取得完整可校验包，未执行未校验文件。现改用已有Windows MSVC CI的实际PowerShell和编辑器，不再把本机依赖当成所有手段都不可用。候选为部署移动前prepared日志、原子JSON回执、deploying状态回退与旧configured兼容；源脚本审查指出旧版中断回执的恢复缺口，须由精确旧main对照和候选实际运行确认。

新增隔离回归使用编译的PE启动器转发CI已有Python/Node/Git，明确模拟Windows包布局。计划验证旧版中断回退拒绝、新版替换/全新部署中断恢复、5项journal边界、原7项PowerShell回归及真实框架doctor后继续原需求。CI通过前#91/#642保持开放，不声明完整独立供应商包、任意断电点、并发安装或回退途中再中断验收。

后续责任：当前Sail-Li/Codex会话，沿独立审查、正式门禁、同一候选CI/main及本单关单回读连续推进。当前证据解析基准为仓库根：`data-collection/before300-20261109-delivery/receipt.json`。

父单：#47；审查来源：#88。需求文档：`design-docs/yanluo-issue-47-igniter-acceptance-20261105.md`（路径相对仓库根）。

已交付依据：PR #57/#62/#67 已合入安装/恢复源码与原生 modal 协调；14 项点火器、17 项桥接及 20 项原生/186 断言等既有证据保留。
已合入提交/审查基线：`879d20f62c1bc7ed462a6a178938e3fdb521e71c`。

剩余验收：

- [ ] 验证真实项目本地及用户级安装位置契约、显式选择与授权、取消/卸载/环境回退和日志。
- [ ] 验证跨编辑器重启的原始消息、需求队列恢复与设置回退，doctor 成功后恢复原需求而不重复执行。
- [ ] 验证 PowerShell 中断及恢复，不把模拟安装成功当真实系统安装验收。
- [ ] 完成原文已承诺 macOS/Linux 部署测试，记录实际平台与工具版本、失败和恢复。
- [ ] 验证最终实际回复链路及可见交互的焦点/层级，真实供应商结果与夹具分别留证。

边界：不重复实现已交付恢复/modal；根据实际环境逐项验收，缺平台/服务保持 unknown。

证据：data-collection/issue47-recovery-r2-20261105.json; data-collection/issue47-modal-20261105.json。

本单由阎罗全仓审查及独立复核形成，后续由司南按真实需求事件派发；创建不等于已执行或生产启用。原父单未满足全部验收，继续开放；本单完成后重新核对父单。

<!-- gonggong-host-git:Sail-Li -->

## 2026-11-09 续办

用户将环境范围收敛为模拟 macOS/Windows。新增四种可执行文件名/位置组合的恢复/回退模拟；15 项点火器回归通过，实际已有 Python/Node/Git 的两种位置选择经独立进程记录/回读/解绑通过。两种选择均在 workspace 状态记录绑定，并未安装/卸载系统软件。既有恢复/modal证据与真实供应商边界保留。

本轮源修订、实测与模拟边界统一引用 `data-collection/before300-20261109/validation.json` 及同目录各项报告（路径相对仓库根）。


## 2026-11-09 当前候选补验与交付结论

本轮继续按用户收敛后的mac/Windows模拟范围记录：15项点火器测试覆盖project-local/user-level两种选择、无后缀/.exe路径、状态重载、幂等恢复、篡改拒绝和rollback；当前配置读取器9项通过。当前编辑器停止/取消后的第二进程还验证原消息、两条补充的内容顺序、snapshot及后端/端点/模型保留，API key不持久化。

原Windows真实PowerShell部署/失败回退/doctor后恢复原需求的旧证据保留其原二进制和脚本映射（`data-collection/ai-chat-debug-20261104/verification.json`及`issue47-modal-20261105.json`）；本轮没有PowerShell执行入口，未新验真实中断过程、完整包安装/卸载与doctor跨重启的组合。环境选择/绑定模拟不等于包安装。#91保持开放，只挂起这些尚缺的组合验收，不回到Linux或x86_64/Clang14门槛。`data-collection/before300-20261109-followup/validation.json`（路径以仓库根为基准）保留实际与模拟边界。
