# 不同工单并行进行画布范围判断

canvas-route-concurrency 对应 [#760](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/760)。画布判断是只读分类。执行意图交回原绑定工单，各范围可在独立的执行实例中等待结果。打开已有工单、核对批准令牌和处理旧历史沿用原有归属规则。验证 A 正在工作时 B 的画布仍可接受派发、产生实际工作和接收确认。[集成设计与验收](tianshu-production-parallel.md)
