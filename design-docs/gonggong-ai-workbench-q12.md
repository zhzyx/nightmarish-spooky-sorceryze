# Q12 断回执后的多宝提交验收

[工单 #1735](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1735)要求确认提交已在目标仓和天璇生效、但发起者未收到确认时，可以从同一工单恢复。前置 [G15](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1805#issuecomment-7075141353) 在 Mac 验证了多宝交付与工单回写。[R06](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1822#issuecomment-7079181171) 在 Mac 验证了物化工程按原调用键对账。本卡在 Windows 实测 G15 的 Git 交付路径。

## 故障与恢复

在系统临时目录建立只有一个待交付提交的分支、裸目标仓和独立天璇数据库。另一个认证编辑者批准请求后，headless 编辑器通过“交付并回写工单”向真实天璇服务提交。只在本机监听的测试中转收到接收方完整成功结果，随即关闭下行 TCP 连接。编辑器报告连接关闭，未取得交付确认。

重启天璇服务和编辑器，从原工单的评论读取原合入请求编号。编辑器用“刷新检查”和“读取目标分支”取回合入状态与目标 SHA。验收器核对以下记录，原始编号、SHA、评论、进程及测试脚本版本均保存在[Windows 回执](../data-collection/gonggong-ai-workbench-plan1-q12.json)。

| 核对位置 | 通过条件 |
| --- | --- |
| 隔离裸仓库 | 从原目标基线到 `main` 只有一个新提交；该提交与原候选、交付标记及目标文件一致。 |
| 原天璇工单 | 重启后只有一条交付评论，包含原请求和目标 SHA；读取前后评论一致。 |
| 持久回执 | 直接只读打开 SQLite，按 `issue.comment` 和 `duobao:<原请求编号>` 查到一条记录。其结果与工单评论和丢失确认中的评论编号一致。 |

## 复跑

从仓库根执行。将环境变量 `Q12_EDITOR` 设为待验收编辑器的绝对路径，使用已安装天璇服务依赖的 Python。实测的 Windows 编辑器原生构建输入为 `8fed6845e89bb027af60d0497cbd9a9ad54a18b9`，服务源码基线为 `2ee48917eb54b82a14c381ffc8cb3c290b49bd14`。

```powershell
python -X utf8 tests/editor/run_workbench_duobao_receipt_loss.py --godot $env:Q12_EDITOR --report "$env:TEMP/q12-readback.json"
```

在同一 Windows 服务基线上，另运行 `test_native_workcopy_commit.py`、`test_selected_commit.py` 以及 `test_merge_queue_api.py::test_delivery_recovers_lost_work_order_write_and_refuses_retracted_target`，11 项通过。FastAPI 的 TestClient 发出一条关于 httpx 的弃用提示。
