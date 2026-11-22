# S03　启动唯一一次本机工作者

已确认任务沿天璇授权、司南预约和本机执行入口取得同一个运行号。运行号取自持久化任务契约的摘要。认证客户端调用 `execute` 或 `status` 可取得 `id` 和 `worker_ref`。后者沿用候选来源中的 `native-worker:<id>`，可跨连接关联到同一工作者。司南收到终态时核对本次预约的运行号与工作者引用，将两者随原有派发回执返回。[S03 原单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1845) · [工作流](../customizations/components/tianxuan/sinan-workorders/native_workflow.py) · [司南派发](../customizations/components/tianxuan/sinan-workorders/native_dispatch.mjs)

SQLite 写事务在运行工作者前将预约转为运行中。对同一张已签认工单再次授权、预约或执行时，服务回读该契约的原票据及当前状态。工作者引用可以在启动前用于定位票据。判断工作者是否实际启动和退出分别使用进程观察和持久关闭记录。对仍然未知的进程，原有占用与核对规则继续适用。[本机工作者](../customizations/components/tianxuan/sinan-workorders/native_worker.py)

## 接收实测

Windows 上用既有 headless 编辑器打开已签署设计，选中程序、动画两项，用原生控件确认程序项。经认证的回环 HTTP 服务在同一套天璇和产物数据库上执行以下操作。测试子进程一启动即自行写入运行号及操作系统 PID，然后等待放行。独立进程日志保留每一次写入。[原生实测入口](../tests/editor/run_workbench_confirmed_native_stage.py)

1. 对同一程序项两次申请授权得到同一票据。首次预约成功，首个 HTTP 客户端发起执行。在响应尚未返回时重复授权、预约和执行，预约返回 false，执行返回 running。
2. 关闭首次执行的 TCP 连接，另建客户端用同一账号重投。服务返回相同的 running 状态、运行号与工作者引用。
3. 放行子进程，通过重连客户端取得终态并再次投递。服务返回 produced，候选的来源引用与运行中观察相同。三个时间点读到同一个 PID、一次进程启动。宿主只记录一次实际关闭，退出码为 0。动画项仍待确认，启动次数为零。[实测回执](../data-collection/gonggong-ai-workbench-plan1-s03.json)

首次实测还发现账号会话在 `await-terminal` 返回时被按访问密钥刷新，导致正常重连收到 401。修复后由原认证中间件重新解析同一份凭据。定向用例验证了账号会话及访问密钥的 bearer、cookie 入口，有效凭据取得终态，等待期间撤销的凭据返回 401。[关联故障 #2026](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/2026) · [终态观察测试](../customizations/components/tianxuan/sinan-workorders/test_native_terminal_events.py)

## 复跑

从仓库根用已安装天璇依赖及 Node 的环境运行。原生实测入口会将候选编辑器及其界面资源复制到系统临时目录，用独立配置启动。下列 `--report` 指向本次运行的输出文件。

```powershell
python tests/editor/run_workbench_confirmed_native_stage.py --godot <候选编辑器路径> --report <结果文件路径>
python -m pytest -q customizations/components/tianxuan/sinan-workorders/test_native_stage_stop.py customizations/components/tianxuan/sinan-workorders/test_native_terminal_events.py
```

本次服务适配由天璇 Python 服务和司南 Node 驱动加载。更新与回退沿原安装流程一并切换已核实的服务、宿主和派发程序版本，复用原数据库。原生控件沿用已签发的编辑器包；实测编辑器摘要、服务代码版本及前置签收随回执保存。[部署入口](../customizations/components/tianxuan/server/native-entry-interface.md)
