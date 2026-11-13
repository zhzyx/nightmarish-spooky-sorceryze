# Gameplay 模块

本模块是原生玩法体系的顶层入口，覆盖玩法对象与生命周期、会话与比赛、专服、网络复制、相关性、预测及宿主适配。

当前先作为聚合细则使用，不预建空子目录。后续新增规范优先插入本文件对应章节；只有形成独立任务边界且需要单独加载时，才按文档路由规则拆分。

## 职责范围

| 职责分区 | 内容 |
| --- | --- |
| 核心对象 | World、GameMode、GameState、Controller、Pawn、PlayerState、Component、Subsystem |
| 会话与比赛 | 连接、认证、业务准入、玩家创建、加入／退出、出生／重生、断线重连 |
| 专服与传输 | Dedicated Server、Session、ENet 及其他可替换传输适配 |
| 复制与相关性 | RPC、属性复制、复制条件、分片、连接视图、优先级、频率和带宽预算 |
| 预测与集成 | 输入序号、服务端确认、客户端预测、校正、插值和代表性示例 |
| 宿主适配 | Godot 场景、节点、信号、Multiplayer 及未来其他引擎后端 |

## 核心不变量

- Controller 与 Pawn 的控制关系双向一致，换控先解除旧关系。
- PlayerState 独立于临时 Pawn 和传输 peer，不因换控、销毁或重生而消失。
- 网络 authority 与 gameplay ownership 分离，客户端控制不自动授予服务器权威。
- GameMode 只在权威上下文运行，GameState 承载可观察状态。
- Subsystem 按作用域管理，反初始化顺序与初始化相反，重复调用保持幂等。
- 核心策略不依赖具体传输或宿主；适配层变化不得反向污染核心契约。

## 验证与资料

- 测试入口统一见 `../testing/README.md`；实际验证范围按平台、候选和测试证据记录。
- 完整设计与历史验收见 [Gameplay Framework 设计](../../design-docs/gameplay-framework-20261106.md)。
- 历史文档中的完成状态不能替代当前代码、Issue、PR、CI 和 main 回读。
