# 并行子工单回传父会话

需求与授权：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/775；父目标 #773。路径以本仓库根为基准。

现有 runner 的契约是独立工作副本派发、私有回执与 review 状态，不含父会话通知。新增能力绑定当前存活父会话、快照、Issue、需求、workspace、设计批准、实际派发批次及工作者编号，复用设计批次通知队列。终态只产生一次通知；模型按原授权核对实际产物与剩余验收。没有隐式设计批准、依赖验收、合入或关闭。外部执行器始终拥有其工作者，编辑器不得降级串行重跑。

每次已启动批次完成后保存宿主观察的摘要文件及 SHA-256，通知只含状态、退出码及原始回执引用，不提升日志内容为指令。缺失或无法解析的回执保持 unknown；失败保持 reconcile_required。停止、关闭、父绑定变化或设计变化不续办；无关会话不被抢占。必要落盘失败保留暂停的本地待恢复通知。冷启动沿既有协议不自动重放。

召回 `gonggong-workspace/editor-dependency-handoff` 的 verified `bind-consumer-release` revision 6：适用于本次生产者到父消费者交接。反例是运输完成或来源字节变化不能放行依赖。本次回归覆盖正常一次通知、失败、未知、停止、无关会话、父关闭、绑定和设计变化、回执落盘失败；未建立业务验收的状态始终保留。

## 构建边界

修改已有 Godot 原生宿主 `editor/docks/ai_chat_sub_agents.cpp`，由 editor/SCsub 编译链接，属于 native 输入，必须生成候选二进制后执行行为回归。不新增模块。宿主接口为现有 design_batches/queued_messages 与 tools/godot_parallel 的 JSON 文件契约；runner 不变。测试脚本是独立 host_tool fixture，不作为产品运行入口。回退为原已验证二进制及对应源修订，保留私有派发回执；不替换当前安装编辑器。

验证计划：原生候选构建键随源码变化失效；候选 --headless 使用隔离编辑器、项目、受控 HTTP 模型及真实独立 runner fixture 进程执行 tests/editor/run_design_batch.py 的 parallel-* 场景。既有 test_parallel_work_orders.mjs 覆盖生产 runner，夹具不代表供应商或真实账号调用。

实际结果见 [验证回执](../data-collection/parallel-parent-continuation-775.json)：九项并行静默场景、既有串行与只读审查场景通过；原生 45 项 / 638 条断言通过；最新 main 的执行器 17 项测试通过。原已安装版本在同一隔离场景中缺少父通知，未替换该安装。最终候选继承 main cc05be55；重新构建核对后的二进制与上述场景测试的字节相同。

实际排查补齐了外部执行器观察生命周期：派发启用已有进程观察，聊天空闲、切换会话和停止仍保留其终态回读。停止按钮仅对当前根会话的存活并行批次可用，并通过既有取消文件契约通知该批次工作者，不取消无关会话。独立审查还收紧历史保存事件，仅已排队的父通知持久化完成才接续，普通历史保存不成为重新派发事件。
