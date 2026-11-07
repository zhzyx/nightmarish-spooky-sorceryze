# 复杂控件的受控语义接口

来源：[父需求 #386](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/386) 与目标接口 #388，沿用户原授权继续，不需要新增模型或工具授权。基线为首批基础接口交付候选；生产前回读实际 main 与工单占用。

范围：F02/F03 尚未覆盖的 PopupMenu 原生 Window 实例、Curve/Gradient 资源编辑器、GraphEdit 节点/端口/连线，以及 Tree/ItemList 激活和上下文业务动作。优先语义命令，不以任意坐标/键盘模拟绕过控件及认证边界。为条目、端口和连接提供分页/值/实例/旧状态/容量说明。密码、exclude、编辑场景自动控件排除和 AI Chat page_only 保持；执行仍走原 tools/consultation/host confirmation/session/Bearer/busy 链路。

验收：macOS arm64 headless 编译、原生拒绝路径与真实隔离编辑器命令往返；延迟弹窗可发现，修改前预览且变化后拒绝。不能把信号发出当成业务已完成，GraphEdit 操作需业务状态回读。容量边界明确，不无差别提高原上限。独立审查、正式门禁及精确 CI/main 回读。像素/IME/原生认证窗口单列，禁止操作用户桌面。

责任：本 Codex 接续至实现、验收及 main；依赖首批基础接口实际接收，不抢占其他工作树。未实现项不计为首批完成。
