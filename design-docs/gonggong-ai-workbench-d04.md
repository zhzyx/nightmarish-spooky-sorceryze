# D04 手工创建并保存设计正文

在 Godot 的 AI 工作台登录天璇账号，打开「设计文档」，点击「新建设计」。填写标题和正文后点击「保存」，天璇为当前账号建立第一个修订。编写时可以留空行分段，也可在同一段中换行。整个流程可在首次对话前完成。[设计条款](gonggong-ai-workbench-plan1.md#d04) · [工单 #1863](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1863)

## 重开与再编辑

关闭文档窗口，再次打开「设计文档」，选择相同文档 ID。状态栏显示天璇返回的修订号和该修订作者的账号 ID，段落菜单可选中整段。点击「编辑正文」会载入当前显示的正文，把修改保存到同一文档的下一修订。文档名相同时仍按 ID 区分。[上游阅读入口](gonggong-ai-workbench-d02.md)

首次保存发送 `POST /api/v1/docs`，修改通过 `PATCH /api/v1/docs/{id}` 携带 `expected_version`。服务端根据业务会话判断写权限和作者。每次成功后，视图按服务返回的文档 ID 和版本重新读取 `GET /api/v1/docs/{id}/versions/{version}`。旧版本发生冲突时保留草稿，可复制后重新打开最新修订。保存结果未知时，使用相同正文和 `call_id` 重试同一请求。[原生工作台](../editor/docks/workbench/business_session.gd) · [天璇文档接口](../customizations/components/tianxuan/server/api.py)

## 构建与复验

变更沿用编辑器内嵌的业务会话脚本，构建时生成 `BusinessSession.gen.h` 并链接进原生侧栏。发布与回退使用对应构建的编辑器；服务沿用已有文档与版本存储。[构建入口](../editor/SCsub)

在仓库根使用安装了天璇服务依赖的 Python 执行以下命令。探针在隔离的临时项目中通过编译后的编辑器控件输入多段正文，保存、关闭、重开并复查作者，再编辑保存 v2。它也覆盖连续点击、服务已写入但客户端收到 503 后重试、使用旧修订编辑和 D02 的只读路径。测试使用本机回环天璇服务及一次性账号和数据库。[定向验证记录](../data-collection/gonggong-ai-workbench-plan1-d04.json)

```sh
python tests/editor/run_workbench_documents.py --manual --godot <候选编辑器> --report <本地报告路径>
```
