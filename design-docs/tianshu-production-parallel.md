# 天枢画布跨工单生产

需求 tianshu-production-parallel 对应 [#758](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/758)。用户在已有天枢工单的输入框发送指令后，可以立即切换到另一张工单继续生产。以已连接的账号和 CLI 执行，每张工单独立收回答复、候选变更、审批和终态。

- [#759](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/759) 覆盖点击发送到身份核验返回之间的导航和草稿。
- [#760](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/760) 覆盖只读范围判断、已有主会话和后台工作者的并行路由。
- #758 整合两段并负责 execute 返回后的继续执行。原操作者、工作区、绑定、工单修订和指令仍有效时，后台执行留在提交时的工单。需要选模型、澄清或批准时，在原工单提示。项目级建单等依赖当前选区的操作继续核对选区。
- [#761](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/761) 独立核对画布、推进对话及已有主会话和零消息工作者的组合，模拟 #706 和 #426 的现场布局。真实工单历史不作为测试输入。
- 同时运行的审批不应引起无关工单的 Git 验证或工作流刷新。已绑定工单的候选校验与执行前批准仍在原入口执行。

验收使用 Windows 静默编辑器、彼此独立的临时 Git 候选、受控服务端屏障和已登录 Codex。检查两次发送是否重叠、停止与迟到回执归属、重启恢复、真实产物及终态，并分别记录现场安装和候选哈希。[验收回执](../data-collection/tianshu-production-parallel-758.json)
