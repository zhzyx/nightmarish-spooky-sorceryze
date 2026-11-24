# D02 在 Godot 打开设计文档

在 Godot 打开 AI 工作台，用「天璇账号」登录业务项目，再点「设计文档」。列表显示当前账号可读文档的标题、修订号和天璇文档 ID。同名文档各占一行。选中一行后，下拉框列出该修订的各段。选择目标段，正文会滚动并选中整段文字。[原始设计](gonggong-ai-workbench-plan1.md#d02) · [工单 #1865](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1865)

## 引用与读取

原生侧栏的 `WorkbenchBusinessSession/WorkbenchDocuments` 接受 `await open_document(id, version, paragraph)`。成功后 `reference` 保存 `document_id`、`version` 和从 1 开始的 `paragraph`。段落由空白行分隔，连续的非空行属于同一段。空文档可打开，引用的段号为 0。正文只读。请求的修订或段号不存在时，视图会清空正文和引用，并显示原因。

视图复用 D14 业务会话，先用 `GET /api/v1/docs` 读取列表，再用 `GET /api/v1/docs/{id}/versions/{version}` 读取所选修订。账号权限由天璇服务核验。文档更新后，旧引用仍指向原修订。切换账号和退出会清除列表与正文。后到的旧响应通过请求代次丢弃。[业务会话与视图](../editor/docks/workbench/business_session.gd) · [账号接入](gonggong-ai-workbench-d14.md)

## 构建与复验

编辑器构建将业务会话脚本生成到 `BusinessSession.gen.h`，侧栏在原生二进制中加载它。更新需要重新构建编辑器。回退可使用上一已验证的编辑器。该视图只读取天璇已有数据。[构建入口](../editor/SCsub) · [侧栏](../editor/docks/workbench/AIWorkbenchSidebar.cpp)

使用装有天璇服务测试依赖的 Python，从仓库根在隔离的编辑器上运行探针。测试会启动回环天璇服务，创建两份同名文档，通过实际侧栏控件选取目标段，然后回读旧修订、缺失修订、越界段号和登出后的控件状态。

```sh
python tests/editor/run_workbench_documents.py --godot <候选编辑器> --report <本地报告路径>
```

Windows 整合候选的 SHA-256 为 `25a5fb5d03593dc257830ddc6d93fafa6322572d99c9d3ae8f4d12b997537ea3`。第一份同名文档的 v1 选中了「第一个目标」和下一行「延续一行」。第二份的 v2 选中了「第二个目标」，回读它的 v1 则选中了「原始段落」。三次都定位到第 2 段。[定向验证记录](../data-collection/gonggong-ai-workbench-plan1-d02.json)

Mac 对上游 D14 的账号观察见[账号验收记录](../data-collection/gonggong-ai-workbench-plan1-d14.json)。
