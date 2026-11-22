# D09 确认指定的设计修订

在 AI 工作台打开「设计文档」并选择正文，点击「设计签认」。弹窗显示文档 ID 和修订号。填写该版的验收条件，点击「确认 vN」。已签认修订再次打开时，窗口显示确认账号、时间和原验收条件。「版本历史 → 阅读原修订」可核对指定历史版本的签认。正文修改或恢复均产生新修订，需要单独签认。[D09 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1858) · [D06 版本历史](gonggong-ai-workbench-d06.md)

D10 与 D13 可通过已有天璇会话读取 `GET /api/v1/docs/{id}/versions/{version}/signoff`。存在的修订返回 `{"signoff": null}` 或含 `document_id`、`version`、`confirmed_by`、`confirmed_at`、`acceptance` 的签认对象。读取遵循文档权限，缺少该修订返回 404。确认人取自服务认证的账号，时间使用服务端 UTC。签认范围为该版设计；拆单与启动执行各自需要后续操作。

对同一路径 POST `{"acceptance":"验收条件"}` 需要编辑身份及该文档的写权限。每个文档修订最多一份回执。相同确认人及相同条件重试会读回原始时间，条件或确认人不同返回 409，可重开核对。编辑器在写入期间冻结条件和目标，遇到回执丢失时保留原请求。关闭弹窗、切换修订或换账号会清理窗口内的签认信息。[天璇领域实现](../customizations/components/tianxuan/server/tianxuan_core.py) · [原生控件](../editor/docks/workbench/design_signoff.gd)

## 构建与复验

脚本经 `editor/SCsub` 编入 `BusinessSession.gen.h`，由原生侧栏挂载。服务启动时给已有 SQLite 库添加按文档和修订唯一的回执表。回退可使用前一个已验证的编辑器和服务，保留数据库中的历史回执。定向探针在独立临时目录启动回环服务及两次 headless 编辑器进程，向确认按钮投送鼠标事件，并覆盖双击、回执丢失、版本变化、历史回读、只读账号、条件冲突和数据库重开。[定向验证](../tests/editor/run_workbench_design_signoff.py) · [验收回执](../data-collection/gonggong-ai-workbench-plan1-d09.json)

```sh
python tests/editor/run_workbench_design_signoff.py --godot <候选编辑器> --report <回执路径>
```

上游 D03 的 macOS 交付已验证会话追溯和精确修订打开，D06 的 macOS 交付已验证历史与恢复入口。本卡原生签认在 Windows x86_64 上复验。[D03 macOS 交付](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1860#issuecomment-7067023618) · [D06 macOS 交付](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1861#issuecomment-7068555775)
