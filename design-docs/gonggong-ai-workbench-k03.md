# K03 逐项授权与本机阶段验收

同一份《开桥机关》设计的第 1 修订拆成程序、动画、音效三张工单。负责人在原生工作台依次点击程序和动画各自的确认按钮。程序停在可运行原型，动画停在动画预览。音效只定义目标，保持待确认。原始条款见[方案一 K03](gonggong-ai-workbench-plan1.md#k03)和[工单 #1715](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1715)。

## 本次结果

| 工单 | 授权终点 | 本机生产进程 | 产物和停止记录 |
| --- | --- | ---: | --- |
| 程序 #1 | 可运行原型 | 1，PID 127100 | `a/bridge.py`，119 字节。检查器实际运行切换函数，连续两次拉杆先升桥、再复位。阶段为 `stage-reached`。 |
| 动画 #2 | 动画预览 | 1，PID 134276 | `b/bridge.svg`，251 字节。检查器从候选读取桥面和旋转动画，在 24 帧/秒的第 24 帧达到水平，并保持最终姿态。阶段为 `stage-reached`。 |
| 音效 #3 | 待确认 | 0 | 提交调度授权返回 HTTP 409，确认修订为 0，无执行号、工作者或产物。 |

原生鼠标确认后，认证的天璇服务受理两张已签名的工单。仓库的 Node 司南入口自动选择、预留、启动并验证这两个阶段。首次实际收到 `reserve`、`start`、`execute` 和 `verify-stage` 请求各 2 次；再次启动同一调度入口只收到 `advance` 和 `inspect` 各 1 次。阶段之后的整合与发布调用均为 0。同一构建另行通过原 A02 场景的确认、重新读取与撤销测试。

程序运行号为 `31f7d8172e02bee04c4de0dd034273f0af5cc976d592046799c8d1ae5945afac`，动画运行号为 `8d28c958bc91844f6f30599f3398008f5f852560495d6e6cee82bda4cfdef521`。每个进程在启动时自行写入 PID、运行号及收到的授权，宿主随后独立记录退出码 0。本机工作者重建的完整终态与天璇接收的生产终态相同。司南的阶段停止回执与天璇的阶段记录相同。工单详情显示的运行号、授权终点、候选和模块修订与上述回执一致。[逐项接收记录与原始产物](../data-collection/gonggong-ai-workbench-plan1-k03.json)

## 在另一台机器复验

准备本仓库支持的 Node、能导入天璇服务与测试依赖的 Python 3.11+，以及与候选原生、内嵌及安装资源一致的工作台编辑器。在仓库根执行以下命令。

```powershell
python -X utf8 -B tests/editor/run_workbench_k03_stage_acceptance.py --godot <候选编辑器> --report <本次报告.json>
```

测试在独立的系统临时目录内通过 `copy_editor` 创建私有编辑器，启动认证的回环天璇服务和独立 SQLite 库。测试的本机工作者使用确定性的程序与动画输入，实际启动子进程、写入工作区，检查器独立读取多宝的不可变候选。结束时关闭编辑器、工作者与服务，移除临时安装、数据库和工作区。每次复验均记录当次的设计 ID、运行号、进程 PID 和检查回执。

核对报告中的 `result.confirmations`、`result.dispatch_calls` 与 `result.replay_calls`，分别查看原生选择、首次调度与重放。每项的 `local`、`closure`、`stage_stop`、`issue_progress` 和 `artifact` 给出物理退出、候选、停止理由、目标接收进度、完整工件内容和 SHA-256。两个生产终态均为 `produced`，两项的阶段检查均为 `passed`，对应停止理由均为 `authorized_stage_criteria_met`。`result.unsigned` 记录音效的授权拒绝与零调度。

## 输入与交接

Windows 实测基于 `8e529a9a9c7a0fc54ba49f2b6da2e801800d5d6f`。本次改动为验收探针、用例和回执。对比已验收编辑器的构建输入修订 `8fed6845e89bb027af60d0497cbd9a9ad54a18b9`，这两个 Git 修订间的 11 个差异文件全部位于 `data-collection/` 与 `gonggong-diting-data/`。本次使用的 Windows 编辑器 SHA-256 为 `748650bf3c4e91bfb4aab2a98b2322a40eb3a4715ef9088d31c946af283f11fc`。报告保留实测代码、测试探针和私有编辑器两份安装资源的 SHA-256。[编辑器来源 PR #2065](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/2065)

开发前工单门禁回读 #1715 为 `status:in-progress`，来源修订为 `682624e4def50dfff5d333badb4c7bffdab0a59fd6201fc4669c450a8606bd47`。直接前置 A05 #1762、K02 #1716、S05 #1812、S06 #1833、S07 #1763、S08 #1792、S09 #1813、S10 #1814、U16 #1793 均已按 completed 关闭。[跨设备认领](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1715#issuecomment-7078274977)
