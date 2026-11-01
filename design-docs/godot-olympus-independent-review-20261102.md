# Godot / Olympus 候选独立审查

需求：`godot-olympus-chat-20261102`，GitHub Issue #2。用户明确授权“安排独立审查，完成后由我批准”。本文件记录真实独立评价，不是用户批准，不替代 Agent 定义准入或宿主授权。

## 分发与上游审查

评价者：`/root/review_upstream`，未修改实现。最终增量结论：已修复合法本地批准被全量同步误判为漂移的问题；当前审查范围未发现新增阻断性代码缺陷。独立执行 `tests/editor/test_olympus_distribution.py`，4/4 通过。

核对完整来源索引、相对路径基准、移动后的候选、来源增删改/撤销/缺失拒绝、候选与正式入口分离、受限本地准入覆盖、主线内自包含 Ariadne 0.4.0 及无旧 scheduler。只有清单指定的许可和明确引用的本地审查证据允许覆盖生成的 pending 记录；共享 admission.mjs 仍验证摘要、主体、基线、独立性、有效期与撤销。

最终审查 SHA256：

- `Olympus/sync/gonggong_sync.py`：`27fab91718e3315c024fcf6c898d095bdc6e1b6447dbff563eab7c508f966a0c`
- `Olympus/sync/sinan_source.py`：`991407d3269af72b77494a490b519105824bb982208bd675d38e1c440b80351b`
- `Olympus/sync/POLICY.md`：`582305ccfba3915260e15701b2e254d217190e8f1ae9b7983e61aa7e638b78f9`
- `Olympus/framework-manifest.json`：`e7806d3eed8a0c47ef65cc5e7580f3ab88f99bdfc222a3cbde989a0de84a7542`

候选摘要：Athena `d824fe0ac121d04835d1cc7f29f95a2509b034b2ec43bdc111d238b369b153fc`；Themis `7d1a0adb2ce5cfe02076f28a7c7810ea94cd57e1bae4dd960df90c803ea93797`；Hermes `16f57ed5dc9cdb831bd57e0ca8ac3ac315355015f3fcd1532c59414e1e4eae3a`。

审查明确限制：来源两个 Agent 原批准仍不匹配；本地实际批准均为 null。`enabled:false` 是待绑定元数据，并不是阻止用户手动运行 refresh 工具的权限隔离。豁免模块默认同目录测试不足以证明前后字节相同，因此主代理另行将重建前快照与交付逐文件比对，结果和摘要保存在验证记录中。

## 原生聊天与事件回执审查

评价者：`/root/review_chat_gate`，只读审查。最终结论：此前发现的阻断性实现缺陷均已修复，当前范围未发现新阻断性缺陷；可进入候选交付审查。独立执行桥接单元测试，7/7 通过。

已修复并复查：Stop 在取消进程前等待上报、重启恢复丢失工具结果、取消/切换时恢复状态残留、同时 flush 同一事件的竞争、Node 环境配置遗漏。已静态核对 HTTP/CLI gate、恢复状态保护、持久 outbox、真实回执、按所选工作区加载唯一实现。原生 12 项测试和七种编辑器场景由主代理执行，独立评价者读取执行证据，未独立复跑原生场景。

最终审查 SHA256：

- `editor/docks/ai_chat_olympus.cpp`：`6a02de567f561b3ae38256f85b2611995182566e78762a857a457c0779ff5c98`
- `editor/docks/ai_chat_dock.cpp`：`43b2250c93e8576a74281cca7b44f904d65aaabb8b6649007e73d675fb5d020d`
- `customizations/components/godot-host/bridge.py`：`1e4826017c425da3b7fcc8c27debb4609de568463c2ecea2b2eecd51db453bb7`
- `tests/editor/run_olympus_chat_gate.py`：`db33bbfa4a2517d2b7b496f078bbab9b6dde90ecd4c73907d2cab8af663ad9ad`

剩余限制：普通模型/工具边界仍同步等待回执，15 秒总预算内可能阻塞 UI；终结和 Stop 投递已异步。真实 CLI 账号、已批准 Agent 的生产运行尚未验收。完整对象摘要见 `integrations/godot/verification-20261102.json`。

## 交付边界

代码审查通过不等于启用许可。先由来源治理链完成共工当前候选的有效准入，再重新准备与复核最终 Olympus 摘要，完成本地三个 Agent 的准入审查并提交用户最终批准。当前不会生成 approved 通行证，不将测试许可或合成模型回复写成生产事实。
