# 从 3D 模型打开关联工单

在已保存的 3D 场景中选中模型，展开天枢紧凑面板。用「关联与内容…」将当前模型与已回读的工单关联。一个模型可以关联多张工单。选中相应行后，「工单详情」和「工单聊天」都会在原生 AI 工作台侧栏打开该工单的咨询。展开工作台后，使用返回侧栏按钮即可回到原场景；关闭侧栏可继续操作原视口。[U14 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1761)

紧凑面板从当前编辑器项目的 `.gonggong/asset-work.json` 读取显式关联。记录按来源仓库及模型资源路径查找，内置模型按场景路径与节点路径查找。工作台使用所选行的完整 GitHub URL 匹配当前天璇项目的唯一目标，读取工单 ID 和当前用户的咨询会话。多义关联在工单详情显示反馈。「答复 / 推进」沿用已有工单操作、表单和确认流程。[模型关联实现](../editor/docks/daqian/spatial_workbench.gd) · [U13 工单映射](gonggong-ai-workbench-u13.md) · [C07 资产归属](gonggong-ai-workbench-c07.md)

切换咨询前，工作台保存原工单的未发送文字和引用。目标咨询恢复后，若仍选中原模型且目标草稿为空，工作台附入场景节点和模型资产的路径与文件修订。已有草稿保留自己的内容。在同一编辑器进程内来回打开工单时，原生侧栏按草稿键保留真实场景和节点的实例标识，再按路径及修订验证引用。重开编辑器时仍沿用已有的失效引用提示。模型对照或咨询本身不会发送消息。

## 构建与复验

紧凑面板和工作台脚本分别由 `editor/SCsub` 生成原生头文件，与编辑器中的业务草稿、模型引用及侧栏代码一起编译。回退使用以前已验证的编辑器及其配套资源。模型关联文件、工单映射和服务侧会话沿用现有格式。

从仓库根，使用安装天璇测试依赖的 Python 执行以下命令。探针在系统临时目录创建隔离的真实天璇服务和编辑器副本。两张同名工单各有一条历史消息，模型位于不同目录且同名。探针点击紧凑面板的关联、详情、聊天和展开返回控件，核对会话、草稿、原视口、相机及选区，并验证跨项目及项目内多义外链。

```powershell
python -B -X utf8 tests/editor/run_workbench_compact_model_route.py --godot bin/godot.windows.editor.x86_64.console.exe --report bin/u14-check.json
```

Windows 本卡实测记录包含候选编辑器摘要、模型关联、访问的天璇接口和目标会话回执。C07 的 macOS 记录覆盖资产归属与权限；本卡的原生往返验证平台见候选回执。[U14 候选与回执](../data-collection/gonggong-ai-workbench-plan1-u14.json) · [C07 macOS 关联验证](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1785#issuecomment-7060361063)
