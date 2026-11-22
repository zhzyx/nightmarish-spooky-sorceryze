# D10　把已确认设计拆为模块任务

在 AI 工作台打开「设计文档」，选中要拆分的修订，点击「设计签认」。确认人和验收条件显示后，有写权限的用户可以点击「拆为模块任务」。对于程序和动画两个可独立验收的条目，分别选择来源段落、当前项目中的业务模块，填写工单标题和该项验收条件，再逐项点击「加入拆单清单」。核对清单后点击「生成工单」，窗口显示天璇返回的工单编号和标题。在「工单详情」输入编号，可以查看逐项验收条件，点击「阅读来源设计」直接打开最初的修订及段落。也可以从版本历史打开早先签认的修订，继续为该版建立任务。[D10 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1857) · [D09 签认入口](gonggong-ai-workbench-d09.md) · [I01 天璇工单](gonggong-ai-workbench-i01.md)

## 来源与回读

会话项目决定可选模块与工单归属。签认是 D09 在指定文档 ID 和修订号上保存的回执。段落号从 1 开始，连续的非空行构成一段。文档进入新版后，已有任务继续指向创建时的修订、段落、项目、模块和验收条件。

- 向 `POST /api/v1/docs/{id}/versions/{version}/tasks?project={project}` 发送 `call_id` 和 `items`。每项包含 `paragraph`、`module_id`、`title` 和 `acceptance`。服务返回 `tasks`，每项包含 `id`、`number`、`title` 和 `design_source`。整个清单在一笔 SQLite 事务中复用 I01 建单和文档关联。未知响应后重试相同清单，沿用原请求标识。相同账号使用同一标识变更请求内容返回 409。
- `GET` 同一路径返回该项目、该修订下可读的实际工单，按编号排列，附原始段落、模块和逐项验收条件。用 `GET /api/v1/issues/by-number/{number}/detail?project={project}` 反向读取 `design_source`。允许阅读原文时，该字段给出 `document_id`、`version`、`paragraph`、`project`、`module_id` 和 `acceptance`。普通工单及无来源文档读取权的账号得到 `null`。
- A01 可按来源中的文档 ID 和修订号读取 `GET /api/v1/docs/{id}/versions/{version}` 和 D09 的同版 `/signoff`，结合逐项验收条件定义任务阶段。[天璇服务](../customizations/components/tianxuan/server/tianxuan_core.py) · [原生拆单窗口](../editor/docks/workbench/design_tasks.gd)

## 构建与验收

`editor/SCsub` 将拆单和签认脚本编入 `BusinessSession.gen.h`，原生工作台在同一业务会话中挂载控件。部署配套编辑器和天璇服务，已有数据库在启动时增加来源表。回退可用上一版编辑器与服务，保留原有工单、关联和精确修订来源记录。

```sh
python tests/editor/run_workbench_design_tasks.py --godot <候选编辑器> --report <回执文件>
python -m pytest -q customizations/components/tianxuan/server/test_design_tasks.py
```

探针在系统临时目录启动独立 headless 编辑器，使用已签认的两段设计、两个项目模块、真实天璇 HTTP 服务及 SQLite。它在数据库成功提交后模拟一次响应丢失，重试生成，核对两张工单和两组关系。改稿后按旧版、工单编号及重开的数据库再次回读。独立并发测试同时从两个数据库连接首次提交同一逻辑请求。[探针](../tests/editor/run_workbench_design_tasks.py) · [定向实测回执](../data-collection/gonggong-ai-workbench-plan1-d10.json)

上游 Mac 已验证从会话打开指定修订，以及版本历史与恢复。D10 的候选编辑器和验证平台记录于本卡回执。[D03 的 macOS 记录](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1860#issuecomment-7067023618) · [D06 的 macOS 记录](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1861#issuecomment-7068555775)
