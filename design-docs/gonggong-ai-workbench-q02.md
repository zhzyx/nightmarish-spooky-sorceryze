# Q02 跨职能工单与权限验收

四个内部测试账号在同一 Windows 编辑器中用命令面板打开 `editor/open_ai_workbench`，通过天璇账号面板登录同一项目。四人均为租户普通编辑者。策划、程序、美术获授该私有需求的写权限，第四位成员未获分享。策划在该需求下发起工单。

| 账号 | 工作台操作 | 实测结果 |
| --- | --- | --- |
| 美术 | 通过「添加本机文件」上传图标，用当前工作台会话提交为概念图 | 附件 v1 与待判断的提交 v2 指向同一份多宝原件。判断人默认为工单发起人策划。 |
| 策划 | 在「我的待判断事项」选择提交 v2，填写意见并转交美术 | 策划的待办清空。美术看到同一修订、双方身份及转交意见，并用自己的账号采纳 v2。 |
| 程序 | 用工作台会话读取该工单已签认的原件，在工单详情发表评论 | Godot 解码得到 8 × 8 的图标，像素为 `#ff7f50`，文件摘要与上传时相同。重新打开天璇数据库仍可读到程序的署名评论。 |
| 未获授权的成员 | 用有效账号打开同一工单，再通过当前会话向同一工单提交评论 | 两次服务响应均为 HTTP 403。详情页显示「没有权限查看此工单」且无工单内容。重新打开数据库，仅有程序发布的评论。 |

本次使用 H05 合入时通过验收的 Windows 编辑器包。探针在系统临时目录创建独立编辑器、项目和两个数据库，启动回环天璇 accounts 服务并接入多宝原生存储。账号切换、文件选择、转交、签认及评论通过控件驱动。提交概念图、消费已签认原件和无权写入检查使用该工作台的业务会话向正式路由发出请求。回执保留处理请求的用户 ID、服务响应、版本、原件摘要和重开数据库后的历史。

## 在仓库根复跑

以下命令使用安装了天璇依赖和 Pillow 的 Python，以及当前候选的 Windows 编辑器包。`--godot` 可指向该包的控制台启动器，其同目录须有对应的编辑器主程序。

```powershell
$result = Join-Path $env:TEMP ("q02-" + [guid]::NewGuid().ToString("N") + ".json")
python -X utf8 tests/editor/run_workbench_cross_functional.py --godot bin/godot.windows.editor.x86_64.console.exe --report $result
```

测试等待编辑器进程退出，并从新的天璇和多宝连接核对写入历史、评论和原件字节。实际运行使用的程序摘要、服务文件、命令及各账号回执见[验收记录](../data-collection/gonggong-ai-workbench-plan1-q02.json)。[原设计](gonggong-ai-workbench-plan1.md#q02) · [Q02 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1738) · [H05 验收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1798#issuecomment-7080572095)
