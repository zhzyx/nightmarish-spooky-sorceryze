# C06　从原生工作台切换业务模块

在编辑器命令面板执行 **Open AI Workbench**。侧栏顶部显示「本机会话」，展开后点「选择业务模块…」，再选天璇返回的模块。选项按稳定模块 ID 定位，同名模块会同时显示 ID。侧栏展开到主屏时会带上当前选择、会话和输入框。[原工单 #1744](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1744) · [方案一 C06](gonggong-ai-workbench-plan1.md#c06)

选择模块时，工作台按当前账号和项目读取 C04 位置及 C02 工单列表，然后读取该位置关联的私人会话。显示的工单编号、标题、位置串、历史消息及当前未确认的设计稿均来自这次回读。同一模块内可选择已有工单或模块概览，离开前将改过的位置交给 C04 保存。读取或保存失败时保留原选择和输入。切换时每个输入草稿按模块、工单和会话暂存在当前工作台进程内。返回「本机会话」会恢复原生编辑器原有的聊天输入。[位置接口](gonggong-ai-workbench-c04.md) · [工单接口](gonggong-ai-workbench-c02.md) · [原生控件实现](../editor/docks/workbench/module_selector.gd)

模块会话的「发送」使用已有天璇私人会话接口，并在本轮附上选定项目、模块及工单。首次进入没有历史的模块时显示概览，首次显式发送时才建立会话。打开选择器、输入草稿和切换模块均不发送消息。在装有 D14 的工作台，选择器从侧栏 WorkbenchBusinessSession 取得业务身份、项目和已认证请求接口，切号或身份失效时清空业务工单、会话、草稿并拒绝旧请求的迟到结果。独立运行 C06 时，宿主可通过环境传入天璇账号的会话令牌 `TIANXUAN_TOKEN`，服务根地址使用 `TIANXUAN_API`（默认本机 8000 端口），项目使用 `TIANXUAN_PROJECT`（默认 `workspace`）。凭据只在当前进程中使用。天璇服务使用 HTTPS，本机回环开发服务也支持 HTTP。[会话与消息契约](gonggong-ai-workbench-c05.md)

## 构建与复验

选择器是已有编辑器工作台的一部分。`editor/SCsub` 将 GDScript 转成与原生工作台一同编译的头文件，修改控件后须重编编辑器。退出候选后，使用上一份完整编辑器与其对应的天枢 UI、看板 sidecar 可回退。[构建边界](gonggong-ai-workbench-b06.md) · [工作台挂载入口](../editor/docks/workbench/AIWorkbenchSidebar.cpp)

安装天璇服务的 Python 依赖，在仓库根运行以下命令。对受测进程清除继承的 `GONGGONG_WORKSPACE`，并将编辑器路径替换为当前平台实际构建的裸可执行文件。夹具使用临时项目、私有编辑器副本、回环 HTTP 服务和隔离数据库。

```powershell
Remove-Item Env:GONGGONG_WORKSPACE -ErrorAction SilentlyContinue
python -X utf8 tests/editor/run_workbench_business_modules.py --godot bin/godot.windows.editor.x86_64.exe --report bin/c06-native.json
```

静默探针通过真实命令面板打开侧栏，从两个同名业务模块执行 A→B→A→B，核对控件显示的工单、评论、页面位置、会话原文和未确认的设计稿，在两个输入框分别留下文字并逐次读回。服务端回读另行检查消息条数、切换时发出的 HTTP 操作及最后保存的位置。探针另外在空白模块显式发送一条咨询，核对新会话和上下文快照。独立卡使用身份适配器夹具验证旧请求确实已经发出，切号后的迟到响应无法填回旧账号数据。[定向运行器](../tests/editor/run_workbench_business_modules.py) · [候选与回执](../data-collection/gonggong-ai-workbench-plan1-c06.json)

此前 macOS 已验证服务端 A→B→A，包含已保存的未确认设计稿。该轮指出原生选择与未发送输入仍缺观察。本卡的原生定向运行平台与二进制摘要见回执，双平台组合接收由 F01 继续。[Mac 观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1744#issuecomment-7060360378) · [F01](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1743)
