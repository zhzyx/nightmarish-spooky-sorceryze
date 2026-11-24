# S06 本机执行的暂时故障与回执核对

天璇以预约时生成的执行号为单位续接。SQLite 返回忙或锁定时，服务重新核对预约、当前阶段授权和本进程的执行所有权。本机预约尚未启动时，司南最多沿原执行号再试一次。已有工作者、已有终态或已有外部适配器预约时，服务保留原运行号和占用，按回执所列条件继续核对。其他数据库故障沿原错误路径上报。[S06 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1833)

如果客户端失去执行响应，调度器先调用 `execution-readback`。服务从原工单读取状态、预约、退出码和候选。随后的 `record-execution-fault` 由服务从当前权威状态构造审计事件，`await-terminal` 沿原工作者读取终态。数据库可以读取但无法写入时，已落库终态仍然可见；调度器将审计失败及原执行号写入本次调度结果。HTTP 身份验证和共享管道的工单范围也适用于这两个入口。[服务实现](../customizations/components/tianxuan/sinan-workorders/native_workflow.py)

## Windows 实测

- 认证 HTTP 入口使用真实 Node 调度器。第二条 SQLite 连接持有写锁，使第一次本机执行失败。解除争用后两次调用沿用同一执行号，实际启动一个生产者并到达授权的预览阶段。连续失败时只留下原预约。已经发出外部预约时，测试记录一次外部预约和零次本机启动。
- HTTP 和实际共享 Node 管道都在生产者完成后丢弃执行回执。两条路径的下一次操作均先读原执行号，各自只启动一个生产者。另测实际进程结束后的存储忙和普通数据库错误。未认证请求被拒绝，受限管道不能读取或登记其他工单的故障。
- 独立审查时，写锁下的只读回执因尝试启动写事务而返回 SQLite 错误码 5。修复后同一把锁下可读退出码和候选，审计写入单独返回 HTTP 503，既有终态可以从 `await-terminal` 读回。夸父记录关联原始运行号与修复候选。[夸父 #2059](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/2059)
- 从已验收的 Windows 编辑器复制临时安装，按仓库 headless 探针在实际界面确认任务。服务回读到一个进程、退出码 0 和同一运行号上的产物候选。编辑器二进制、天枢 UI 与面板包摘要及实测调用随原单留存。[实测回执](../data-collection/gonggong-ai-workbench-plan1-s06.json)

从仓库根复跑定向用例，可从 JUnit 属性读取原执行号、生产者记录与接收回执。

```powershell
python -m pytest -q -o junit_family=legacy customizations/components/tianxuan/sinan-workorders/test_native_fault_recovery.py --junitxml=s06.xml
```
