<!-- gonggong-request:yanluo-issue-9-source-host-binding-20261105 -->

# 接通 GitHub 来源真实认领、执行与报告宿主回执

父单：#9；审查来源：#88。需求文档：`design-docs/yanluo-issue-9-source-host-binding-20261105.md`（路径相对仓库根）。

已交付依据：PR #65/#75 已交付来源读取、revision 校验与可信宿主回调契约；8 项夹具及真实 #9 来源读取不证明执行宿主已绑定。
已合入提交/审查基线：`48d6b51f4047151377eb61c412eedc885083401c`。

剩余验收：

- [ ] 绑定当前共工/Codex 权威来源、真实操作者和跨操作者原子认领，核验陈旧 revision 拒绝。
- [ ] 实际连接 compareAndStart/start、ack、report、verifyTerminal，记录一次代表任务真实执行及失败/未知回执恢复，未知不重复派发。
- [ ] 登记来源与真实 Diting 文件/交付回执，区分 configured、delivered、consumed；核对与 #72 在途调度实现的接口和责任，不替代其候选。

边界：仅当前事件驱动宿主接入；不恢复 Olympus 运行入口、不设定时扫描、不默认要求后台服务或独立 HMAC CLI。

证据：customizations/components/issue-workorders/github_source.mjs。

本单由阎罗全仓审查及独立复核形成，后续由司南按真实需求事件派发；创建不等于已执行或生产启用。原父单未满足全部验收，继续开放；本单完成后重新核对父单。

<!-- gonggong-host-git:Sail-Li -->

## 设计定版确认：当前操作者代表任务

用户已批准 #72 集成候选持续到验收合入。本节仅用于已准入候选的真实宿主验收，不改变原三项验收或授权业务发布。两个工作副本只读执行，不提交、合并、推送、改 Issue 或操作运行中的编辑器。模型能力目录限定当前宿主实际已验证的文件读取能力；请求型号与实际路由仍分别记账。

## 生产工单

1. 只读核验能力选择入口
   读取 framework/modules/sinan/dispatch.mjs，确认导出的模型选择函数名为 selectModel，在结果中给出该函数名及 ISSUE90_MODEL_SELECTION_OK。不修改任何文件。
2. 只读核验派发回执关联
   读取 framework/modules/sinan/dispatch.mjs，确认成功派发结果包含 ticket、key、state、receipt，在结果中列出这四个字段及 ISSUE90_DISPATCH_RECEIPT_OK。不修改任何文件。
