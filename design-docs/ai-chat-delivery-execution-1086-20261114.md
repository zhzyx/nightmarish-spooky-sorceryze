<!-- gonggong-request:ai-chat-delivery-execution-1086-20261114 -->
父需求 #1086，实施父项 #1211。用户已明确将 #1086 全部实现与交付交给本会话；本子项仅拆分已授权后台非GUI执行职责，当前接收者 Sail-Li 组织原生工作者，全部候选汇入同一个1086集成PR，不单独抢占交付。

范围：将AIChat 交付执行器去除 View 依赖的真实执行状态与进程/文件/回执处理迁至独立 RefCounted AIChatDeliveryExecution，主工作者负责旧Dock转调及最终后台owner。新工作者独占新增 editor/docks/AIChatDeliveryExecution.h/.cpp 与 tests/editor/TestAIChatDeliveryExecution.cpp；不改其他工作者文件。保留全部原批准、候选、恢复、取消和终态边界，禁止借回调让Dock继续实际执行。

验收：
- [ ] 独立执行器拥有其领域状态与实际副作用，保留原语义和恢复协议。
- [ ] 无GUI最小本机进程/文件/回执测试通过，明确未执行真实发布或切换安装。
- [ ] 主工作者真实接线、独立核查、原生/WindowsCI及main随1086完整交付。

独立实施边界由当前AIChat主工作者确认；源码原件冻结在任务私有收据供审查，本文件保持完整父子溯源，不替代父验收。
