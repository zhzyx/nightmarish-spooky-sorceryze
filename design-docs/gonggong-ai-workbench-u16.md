# U16　引用已注册面板的字段并预览修改

在示例工程的 **Project Brief** 页聚焦 **Summary**，从命令面板打开 **Open AI Workbench**。侧栏列出页名、插件路径、字段路径和当前值。发送后，本条消息的 `context_snapshot.page_field` 保存该值和可用动作。重新打开页面并聚焦 **Milestone** 可以带入只读里程碑。聚焦 **Private Note** 时沿用 U12 的页面级引用，草稿留在原控件。[示例工程](../samples/gonggong-workbench/project.godot) · [面板注册](../samples/gonggong-workbench/addons/project_brief/plugin.gd)

## 注册和授权

插件通过现有 `EditorPlugin.add_dock(page)` 注册 `EditorDock`，在该页以 `workbench_fields` 元数据声明可读的 `LineEdit`。键是相对于该页的实际控件路径，值为 `read` 或 `replace_text`。例如 `{"Brief/Summary": "replace_text", "Brief/Milestone": "read"}`。只有当前聚焦且已声明的字段能进入本条消息。密码框、命中当前聊天凭据脱敏规则的文本和超过 4096 个字符的字段回退到页面元数据。读取权限独立于修改权限。已声明替换但当前不可编辑的控件也只提供读取。

沿现有模型工具 `editor_action` 或已连接本机编辑器的 `route_engine_message` 提交 `action=replace_page_field`，`target` 和 `revision` 取自消息中该字段的 C05 引用，`value` 是新的单行文本。应用前由原生宿主校验当前工具权限与工作模式，并在确认框中列出确切的目标、修订、旧值和新值。操作者可以取消或批准这一次修改。正在使用天枢工单确认卡的模型操作沿用原有卡片。编辑器在实际确认回调中重新获取当前页面和字段，核对实例、声明、可编辑状态及原值，随后只设置这一控件的文本并发出它的 `text_changed`。接收方回读新引用。示例据此把摘要保存在当前工程的编辑器元数据中。

定位符包含模块、页名、字段路径与字段实例，修订绑定项目、编辑器进程、页实例、定位符、文本和编辑权限。页面改名、被关闭、移除声明、目标值发生变化或换项目后，需要重新从当前页面取得有效引用。排队消息使用发送时冻结的内容。字段操作在原生执行入口重新核验引用。A03 的生产工单和阶段签认沿天璇现有入口执行，本卡的单字段确认作用于当前编辑器操作。[原生引用](../editor/docks/workbench/AIWorkbenchReference.cpp) · [字段操作](../editor/docks/workbench/AIWorkbenchPageField.cpp) · [A03](gonggong-ai-workbench-a03.md)

## 验证与回退

从候选源码根运行以下命令。两项测试使用私有编辑器副本、系统临时工程、headless 控件信号和本机回环模型。U16 再经现有本机 HTTP 编辑器接口提交动作，在原生确认框核对预览，并检查目标控件、项目元数据和请求结束回执。同一可执行文件在同一工程读取三次插件文件，依次验证原声明允许替换、更新后只读、恢复原文件后再次允许替换。U12 原测覆盖未注册字段的马良和 R4 Notes 页面。原生变更需要重建编辑器；示例插件随工程源码加载。回退到此前已验证的编辑器及配套资源，并停用示例工程的 Project Brief 插件，项目元数据会保留。[定向探针](../tests/editor/run_workbench_page_field.py) · [实测回执](../data-collection/gonggong-ai-workbench-plan1-u16.json)

```powershell
python -X utf8 tests/editor/run_workbench_page_field.py --godot bin/godot.windows.editor.x86_64.exe --report bin/u16-fields.json
python -X utf8 tests/editor/run_workbench_page_reference.py --godot bin/godot.windows.editor.x86_64.exe --report bin/u16-u12.json
```
