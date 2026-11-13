# M2 PR4：断线重连、网络损伤与优雅停服

## 范围

- 断线保留 Session、Entity 和权威状态 5000 ms；正确凭据恢复同一 SessionId／EntityId，换绑新 PeerId 并轮换令牌。旧 Peer、错误令牌、活跃会话重复重连和超时恢复均被拒绝。
- 断线实体暂停输入消费和快照。客户端以恢复 welcome 的权威状态重建预测基线，保留下一本地序号；传输未确认集合只移除已确认输入，其余经新 Peer 重传，不额外执行本地模拟。
- 服务器输入按序号去重、排序，只消费最后确认序号的下一输入，每实体每 tick 仍最多执行一个输入。客户端每 32 ms 重传未确认输入，不额外推进预测。
- `ImpairmentTransport` 装饰真实发送路径，提供固定种子延迟、抖动、丢包和硬容量队列；端到端场景真实丢弃第一个输入，以重传和权威确认完成同样的 24 步移动。
- B 在 A 断线期间进入 `stale_held`，恢复后收到服务器时间更新的样本并重新进入 `interpolated`／`held`，不使用外推完成验收。
- `BeginDrain` 停止新准入并返回 `server_draining`（reason 8），现有客户端收到带 deadline 的通知后确认。服务器回送 `DrainAcknowledge` 后，客户端再回送 `DrainComplete`；服务器只将收到 `DrainComplete` 的会话计为完成，客户端在发送完成确认后才允许正常退出。任何一方的确认缺失、超时或提前物理断开都不能冒充优雅停服。
- 立即断开与 `DisconnectLater` 明确分离。可靠拒绝和正常停服使用后者，避免 ENet 立即断开清空待发送队列；重连故障注入仍使用真实旧传输断开。

## 实际验证

- macOS arm64／Clang：20 个运行时测试、250 条检查通过；构建目录与仅复制二进制的目录均通过正向和负向场景。
- A 在新 PeerId 上恢复原 SessionId／EntityId，发生可解释校正后最终确认 24、未确认历史为 0、位置为 `3.072`；损伤统计恰好丢弃一个输入，队列高水位不超过显式容量 16。
- B 依次产生初始插值、`stale_held` 和恢复插值，恢复样本服务器时间大于陈旧样本时间。服务器收到两个不同会话的停服确认，强杀数为 0。
- 针对 macOS CI 中服务器成功而客户端失败的问题，停服补充服务器响应与客户端 `DrainComplete` 三步确认。新协议连续 12 次真实三进程验收均产生两份服务器完成日志和两份客户端关闭日志，Sanitizer 与负向停服场景同样通过。
- 负向场景让 B 停止确认、C 在 drain 后加入：A 正常退出，B 与 C 明确失败，服务器记录一次超时、一次强制作废并返回失败；C 实际收到 `reason=8`、`fatal=0` 的拒绝。
- ASan／UBSan 下相同正负场景通过；M1 为 16 个用例、200161 条检查，Trace 保持 `f55d1f5bc85bb72376d3f31cdf9b64aac91e714b6556dbce1663c1db7995924c`。
- 85 文件无 Godot 源码树重新构建并通过相同验收及三份源码＋真实链接契约。服务器／客户端各 24 个对象和 1 个静态库，测试 31 个对象和 1 个静态库；69 个源文件、104 条本地包含无违规。
- clang-format 22.1.5、Ruff 0.17.1、第一方 codespell 2.4.2、构建工具测试和契约单元测试均按实际命令验证。
- 在 `main@f83f680a7570a69ed678dd14e73e0a9de96e74db` 上完成全部集成复验。原生失效使 native key 从 `bfa8edd91db4d63e4053b2cf8ed47252812c79f693a57fe8e9161804d1760db5` 变为 `f0849f2929de506064b97e32010c34a144e4ce5ca81799e98ba1b91c67f7f9c0`，默认启动从 1 tick 变为 2 tick；恢复后键和行为完全一致。

证据：`data-collection/engine-next-headless-runtime-m2-pr4-verification.json` 与 `data-collection/engine-next-headless-runtime-m2-pr4-close-protocol-r2.json`；模块构建边界证据由 `engine_next/build-impact.json` 的 `evidence` 字段定位。

## 未验证与后续

- Windows MSVC 和 Linux x86_64 仍需精确候选 CI 实测，不能从 macOS 外推。
- 本切片不包含真实三进程 10,000 tick 长稳、全部网络队列高水位、发布包检查或完整 legacy 共享 Reconciler 适配；#1042 保持开放并继续第五片。
