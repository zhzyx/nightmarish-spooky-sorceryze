# GitHub Issue 创建（可选）

路径以工作区根解析。此模块是司南可选的 Git 工作流接入工具，不新增 Agent。仅在具体任务获授权接入 Git 工作流并选用本模块时，才按任务需要查重、关联或创建 Issue；关闭时共工框架基础没有外部 Issue 前置要求。不会自动启用 Godot 接入。

在目标工作区根准备 selected-workspace.json。三个字段分别标识 GitHub 仓库、工作区及实际标签，例如：

```json
{"repository":"zhzyx/nightmarish-spooky-sorceryze","workspace_id":"gonggong-workspace","workspace_label":"workspace:gonggong"}
```

请求 JSON：request_id（小写字母/数字/连字符）、title、body、type、owner、acceptance、authority_ref（工作区相对的真实授权证据）。先预览：

```text
python customizations/platforms/work-management/github/git-issue/issue_create.py --workspace selected-workspace.json --request request.json
```

用户/已授权宿主选择方案后，在任务自己的 settings.json 中设置 enabled=true 和预览的 approved_plan_sha256；原文或目标变化必须重新选择摘要。已有用户明确授权可据此选择，无需每个原子动作重复询问。配置文件本身不认证身份或产生权限。

```text
python customizations/platforms/work-management/github/git-issue/issue_create.py --workspace selected-workspace.json --request request.json --settings selected.json --session actual-session.json --gh /explicit/path/to/gh --apply
```

建议通过 diting-host.py run 包装此命令，失败也记录；apply 自身通过同一共享入口记录创建前和回读事件。先核验实际采集绑定和代表任务回执，缺数据回执不发起远端创建。跨聊天统一使用 repository+request_id 及同一协调者；`<!-- gonggong-request:... -->` 精确查重，API 全页读取同时包含关闭工单，已有单复用、不重新打开、不重写状态。type/status/workspace 标签来自计划，初始 needs-decision 只是记录状态，不授予执行权限。

读取 GitHub 实际认证 login 后附 `host-git-account` 标记。回执区分当前操作账号与原 Issue author，并保存更新时间、正文摘要、计划摘要。创建前持久 claim，本地文件锁防同工作区重复执行；不同机器仍须一个实际创建协调者，GitHub 没有此自定义身份的原子唯一约束，不能声称全局恰好一次。发现多个同标记 Issue 时交人工对账；超时/未知响应先回读，找不到也不自动重建。未发出命令的已确认失败同样由宿主核对后决定新尝试，不自动删除 claim。

跨聊天协作只在用户授权范围内通信。当前工作区的宿主接入复用 customizations/components/issue-workorders；本模块只共享输入输出契约，不借用其他执行实例的身份、准入或采集绑定。现有工单的并发编辑、发布、自动监听不在本版本范围。

迁移后的对象须由宿主重新核验。旧批准仅作历史证据。
