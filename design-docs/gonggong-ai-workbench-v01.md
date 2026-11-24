# V01 按对象修订读取快速验证回执

认证客户端读取 `GET /api/v1/native/workflow/tasks/{key}/validation/{module}/{path}`。任务凭据、历史文档的可见性和对象写入范围沿用编辑起始修订入口。当前版本来自模块头，历史回执来自本任务对具体候选运行的已安装工具。每份回执包含模块修订、对象摘要、工具、结论和可定位日志的证据 ID 与摘要。只读查询不会运行检查。

工作台可直接显示响应的 `current.state` 和各工具状态。已检查的当前修订可读到 `passed` 或 `failed`。编辑产生新修订后读到 `pending`，原修订仍保留在 `receipts`。存储拒绝把已撤销的回执用作有效通过依据。对当前任务之外的对象，服务继续执行既有权限检查。[实测回执](../data-collection/gonggong-ai-workbench-plan1-v01.json) · [原工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1820)
