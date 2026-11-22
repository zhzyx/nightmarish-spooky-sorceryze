# S09　按真实终态核收结果

[工单 #1813](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1813) 属于 [方案一 S09](gonggong-ai-workbench-plan1.md#s09)。前置 [S04 #1842](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1842) 已将实际步骤和状态写入天璇工单详情。S09 的接收者是天璇本机工作流的终态观察与阶段验收入口。平台在确定执行进程退出、生产者有权提交的输出落库且终态持久化后开放检查。

## 工作流与故障恢复

| 从正常入口观察 | 状态与证据 | 接收者行为 |
| --- | --- | --- |
| 工作进程已发起，工作者存储读写出错 | `execute` 返回 409，原执行保留在 `held`，主调方持有原执行键 | 使用相同键调用 `reconcile` 或 `await-terminal` |
| 存储可读，能核实进程退出，但候选或完整终态还不可用 | `closed-unresolved`；工单进度的候选为空 | 释放物理占用，阶段检查队列保持为空。等待终态返回专用 409；原始执行记录可继续核对 |
| 存储恢复，已有完整宿主输出封存 | `reconcile` 校验原任务、进程退出、输出摘要和当前写权限，幂等接收候选并持久化终态 | `produced` 开放检查，经检查器读取该版本实际文件，方可产生阶段结果 |
| 仅进程退出落库，输出封存本身回滚 | 同一执行保持 `closed-unresolved` | 恢复数据库写入后仍缺原始字节证据。工作目录后续编辑无法补作该回执 |

无法核实物理退出时沿用现有占用与核对规则。独立终态数据、源修订和写权限的验证沿用 `NativeWorker`；本卡改变天璇宿主适配收到 SQLite 错误后的状态回读与提示。既有 `produced`、阶段验收和依赖事件继续按原契约消费。实现使用另行加载的天璇 Python 服务，Windows 编辑器和内嵌资源沿用已验收构建。

## 定向验证

测试通过已登录的用户调用天璇 HTTP 接口，确认预览阶段、保留执行占用并实际启动一个 Python 工作者。它输出蓝色圆形 SVG 后退出。隔离数据库中的触发器分别让候选接收、最终工作者终态、原始输出封存的事务回滚。等待及直接检查均在产物不完整时受阻。恢复写入前改写工作目录；前两种情形仍取得原始 SVG，第三种继续待核对。正常验收使用独立内容检查器读取不可变候选。每例回读同一工单的执行进度并核对实际启动次数。

从仓库根用接入天璇依赖的 Python 执行以下命令。编辑器参数指向包含随附资源的 Windows 编辑器包。

```powershell
python -m pytest -q customizations/components/tianxuan/sinan-workorders/test_native_output_settlement.py
python tests/editor/run_workbench_confirmed_native_stage.py --godot <编辑器路径> --report <本次输出.json>
```

[Windows 定向实测与接收回执](../data-collection/gonggong-ai-workbench-plan1-s09.json) 记录实测文件版本、运行键、失败的事务边界、产物版本、阶段验收及同一受验编辑器的 headless 结果。验收交接对象为 [K03](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1715)、[Q03](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1726) 和 [R07](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1803)。各后继仍依其完整前置验收推进。
