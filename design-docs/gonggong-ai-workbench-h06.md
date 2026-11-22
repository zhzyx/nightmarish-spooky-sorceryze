# H06　让程序在动画待选时继续运行

任务可以依赖某张工单上的一份创意提交。工作台用户在 H05 的「我的待判断事项」或「并排比较候选」里采纳或退回该版本。司南在等待期间继续调度其他已授权工作。动画后继取得的执行票据包含上游工单、提交版本、签认事件版本、签认人、修订、路径和文件摘要；工作副本从这份不可变修订取得输入。[H06 设计条款](gonggong-ai-workbench-plan1.md#h06)

## 安排依赖与选稿

在下游的 `POST /api/v1/issues/{id}/work/flow/dependencies` 请求中，计划方提供完整的上游 ID 列表，并在可选的 `submission_versions` 中指定需要等待的创意提交号。例如下列请求将一项动画后继绑定到上游第一次提交。

```json
{
  "expected_version": 0,
  "call_id": "link-first-storyboard",
  "dependencies": ["iss_storyboard"],
  "submission_versions": {"iss_storyboard": 1}
}
```

`GET /api/v1/issues/{id}/work/flow` 返回每条绑定的 `judgment` 及是否已采纳。计划方可用完整映射更换等待的版本，传空映射可恢复整单依赖；旧版 I04 控件编辑上游集合时保留未移除的版本绑定。保存与重放沿用现有的权限、版本检查与循环检测。[依赖服务](../customizations/components/tianxuan/server/issue_flow.py)

经阶段签认的后继由已安装的司南接收进程读取。它同时观察缺少人类决定的支路和调度已就绪工单。天璇在人的操作提交后通知订阅者；接收者重新读取当前授权、其余直接前置和绑定版本。全部条件满足时，接收者按正常的预约、生产和阶段检查流程处理原票据。退回的版本保持阻塞，改选另一版本须由计划方更新该支路。接收进程在离线期间错过决定时，重新连接会从数据库读到该决定和已有执行号。[调度器](../customizations/components/tianxuan/sinan-workorders/native_dispatch.mjs) · [天璇任务契约](../customizations/components/tianxuan/sinan-workorders/native_workflow.py)

## Windows 验收与复跑

从仓库根给天璇测试 Python、Node 和已验收的 H05 编辑器运行以下命令。首条用例在同一服务中签认程序与两个动画后继，并启动一个真实 Node 接收进程。程序的实际工作者先退出并通过阶段检查，两张动画票据仍待人选稿；工作台采纳第一版后，该后继进程读取签认原件，生成结果并退出。第二版退回；重复签认与重开接收进程各增加零次生产启动。另一用例使用同一原件两次提交，验证旧绑定在改选后失效。命令将 JUnit 和独立夹具置于本次系统临时目录。[用例](../customizations/components/tianxuan/sinan-workorders/test_native_judgment_branches.py) · [原生控件探针](../tests/editor/workbench_judgment_branches.gd) · [候选与实测回执](../data-collection/gonggong-ai-workbench-plan1-h06.json)

```powershell
$h06Python = 'D:/GongGong-work/tx-venv/Scripts/python.exe'
$h06Temp = Join-Path ([IO.Path]::GetTempPath()) ('h06-' + [guid]::NewGuid().ToString('n'))
New-Item -ItemType Directory -Path $h06Temp | Out-Null
$h06Suite = 'customizations/components/tianxuan/sinan-workorders/test_native_judgment_branches.py'
Remove-Item Env:H06_TEST_EDITOR -ErrorAction SilentlyContinue
& $h06Python -X utf8 -m pytest -q -p no:cacheprovider -o junit_family=legacy $h06Suite --basetemp "$h06Temp/service" --junitxml="$h06Temp/service.xml"
$env:H06_TEST_EDITOR = 'D:/GongGong/data-collection/receipts/1709-after-k03-20261122/accepted-2094-editor/godot.windows.editor.x86_64.console.exe'
& $h06Python -X utf8 -m pytest -q -p no:cacheprovider -o junit_family=legacy $h06Suite --basetemp "$h06Temp/native" --junitxml="$h06Temp/native.xml"
```

部署时配套更新天璇及司南接收器。新增 SQLite 表记录现有依赖的具体提交版本。回退前保存数据库、结束本次工作者和接收器，配套恢复旧服务、派发器及回退前约定的数据库快照。H06 的服务代码和测试探针独立于编辑器嵌入资源，Windows 复用了 H05 已验收的编辑器包。
