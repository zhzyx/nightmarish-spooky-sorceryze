# I14　呈现附件和产物引用

从 Godot 命令面板打开「Open AI Workbench」，登录天璇项目并读取工单详情。「附件与产物」列出当前账号有权读取的提交，最新提交在前。每项显示类型、文件路径、工单提交序号与多宝修订前缀，工具提示给出来源模块和完整修订。选择一项后点击「另存所选版本…」，再选择本地位置。[方案一 I14](gonggong-ai-workbench-plan1.md#i14) · [工单 #1832](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1832)

## 工单及文件权限

列表入口为 `GET /api/v1/issues/by-number/{number}/artifacts?project=...`。天璇在同一读事务中核对租户、项目、工单及祖先需求访问权，从 `issue_work_events` 的 `work.submit_asset` 历史投影可见文件。每条记录包含工单事件 `version`、`kind`、`module`、多宝 `revision`、逻辑 `path` 和提交时的 SHA-256 `digest`。权限来自原始多宝模块，包括私有需求、生产目录与整合产物的来源权限。[服务投影与读取](../customizations/components/tianxuan/server/work_management.py)

下载入口为 `GET /api/v1/issues/by-number/{number}/artifacts/{version}?project=...`。每次下载重新核对工单和原文件权限，从该工单的提交事件取得绑定，以当时的多宝修订读取并复核摘要。工单提交序号与多宝修订分别标识引用和内容。两次提交即使路径相同，也能从详情分别读取。403 表示访问权不足，404 或 409 表示工单、提交或底层文件已失效。原生控件在用户选择的目录接收文件，复核摘要后替换目标。退出、切换工单或改变版本会清除待接收的旧结果。[HTTP 入口](../customizations/components/tianxuan/server/work_management_api.py) · [原生控件](../editor/docks/workbench/issue_artifacts.gd)

已有概念图和模型提交可直接显示。普通附件沿用 `work.submit_asset` 的模块、修订、路径、`expected_version` 和 `call_id`，类型为 `attachment`。它绑定已存在的多宝对象，历史重复请求沿用天璇幂等回执。Godot 导入仍要求当前概念图或模型通过人工审批。选择本地文件上传及绑定交由 [I18 #1759](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1759)。

## 构建与复验

`editor/SCsub` 将 `issue_artifacts.gd` 嵌入 `IssueCreation.gen.h`，业务会话脚本嵌入 `BusinessSession.gen.h`，都由 `AIWorkbenchSidebar.cpp` 消费。侧栏把控件挂到 I02 详情，复用原会话鉴权、项目绑定和身份变化信号。服务沿用已有业务事件表与多宝存储。部署配套的编辑器和天璇服务，回退时恢复上一组已验证版本，保留历史事件与文件。[I02 详情](gonggong-ai-workbench-i02.md) · [构建输入](../editor/SCsub)

```sh
python tests/editor/run_workbench_issue_artifacts.py --godot <候选编辑器> --report <本地报告路径>
python tests/editor/run_workbench_issue_detail.py --godot <同一候选编辑器> --report <本地报告路径>
python -m pytest -q customizations/components/tianxuan/server/test_issue_artifacts.py customizations/components/tianxuan/server/test_work_management.py customizations/components/tianxuan/server/test_approved_asset.py customizations/components/tianxuan/server/test_godot_inputs.py customizations/components/tianxuan/server/test_native_api.py
```

原生探针通过命令面板进入侧栏，在隔离工程使用真实 HTTP 服务及只读账号。两次保存同名路径的不同二进制文件，并将保存的字节与原始提交比对。第三次提交的底层字节已移除，探针核对 409、可见失效提示和目标路径状态。服务实测另覆盖项目、租户、私有祖先需求和原文件授权撤销。[候选及验证记录](../data-collection/gonggong-ai-workbench-plan1-i14.json)
