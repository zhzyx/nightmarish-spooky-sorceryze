# 天枢 Issue 内的并行指令派发

用户在天枢的 Issue 内发出指令。现场 #706 正占用主执行者，#426 已有独立 worker 绑定及空历史。#426 的画布输入框返回“请求失败 · AI 对话正在处理另一项工作，请保留草稿稍后再试”。本单从界面发起独立回归；宿主、账户、仓库、Issue、需求标识均绑定发起者。关联父单 [#748](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/748)，产品变更与 CLI 场景跟踪 [#758](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/758)、[#759](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/759)、[#760](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/760)。[本单 #761](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/761)

静默编辑器在隔离仓库运行，测试用回环模型使用两道屏障。画布用例等到 A 的范围判断请求到达才切换 B，两个范围判断均到达才返回 execute。两份工单执行请求同时到达后才返回需确认的命令提案。验收读取两份候选和令牌，交换令牌须被拒绝，取消 A、批准 B 后只允许 B 的候选执行一次。前台应保持在 B。历史组合用例先通过天枢建立主会话历史与空 worker，退出并使用同一隔离项目重启编辑器，回读原绑定。随后通过“工单对话与模型”的 Send 按钮提交非直发工单，再打开、离开已经分配给第二份工单的空工作者，从第二份工单的画布发出指令。工单服务及模型均使用测试数据，真实用户指令仅作现场溯源。

现有 #723 回归覆盖原生会话绑定、跨重启历史与草稿；本单单独核对普通 UI 是否进入相同的执行链。按本租户 editor-dependency-handoff 域召回结果，接收时核对实际构建和 UI 资源摘要，候选变化须复验。
