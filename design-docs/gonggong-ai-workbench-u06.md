# U06　从弹窗与辅助窗口请求 AI

在编辑器管理的子窗口中按 **Ctrl+Alt+I**（macOS 为 **⌘⌥I**）打开 AI 工作台。独占模态窗口也响应命令面板快捷键，默认是 **Ctrl+Shift+P** 或 **⌘⇧P**。快捷键设置中的 **Ask AI in Current Window** 可重新绑定。来源窗口保持打开。[原工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1745) · [设计条款](gonggong-ai-workbench-plan1.md#u06)

工作台使用原会话的输入框、消息列表、发送逻辑和模型配置。选择 **Quote current content** 将来源窗口标题与焦点输入框的选区追加到草稿。没有选区时，引用输入框的文本。普通提示框还可引用提示正文。可在发送前编辑引用。密码框和编辑器标记为受保护的字段不会提供该按钮。发送采用原会话的权限检查。点击 **Return to Window** 会把会话控件放回主屏或原侧栏，并恢复来源控件的焦点、文本选择行为及其原有设置。

## 构建与复验

窗口路由属于现有原生 AI Chat 停靠面板。构建输入包括 `editor/docks/workbench/AIWorkbenchWindow.{h,cpp}`、`editor/docks/workbench/AIWorkbenchSidebar.cpp` 和 `editor/docks/ai_chat_dock.h`，路径从仓库根解析。SCons 通过已有的 `editor/docks/SCsub` 的 `workbench/*.cpp` 规则编译链接。运行时依赖 Godot 编辑器场景树、Window 的视口输入、原生会话控件和工单 U02 的侧栏。恢复上一版已验收编辑器与其配套运行包即可回退。[路由实现](../editor/docks/workbench/AIWorkbenchWindow.cpp) · [侧栏注册](../editor/docks/workbench/AIWorkbenchSidebar.cpp)

从候选源码根执行。测试使用系统临时目录中的编辑器副本、独立用户目录和仅监听回环地址的模型。将进程环境中的 `GONGGONG_WORKSPACE` 清空，确保编辑器副本从空项目启动。

```powershell
Remove-Item Env:\GONGGONG_WORKSPACE -ErrorAction SilentlyContinue
py tests/editor/run_workbench_window.py --godot bin/godot.windows.editor.x86_64.exe --report bin/u06-window.json
```

测试从会话页签的重命名操作进入原弹窗，在原生编辑器设置的 General 筛选框重现此前 Mac 记录中的选区，并在运行中新增的辅助窗口验证多行输入框和密码框。探针向对应窗口实际派发平台组合键，核对发送、回复、返回及源窗口销毁后的行为。[探针](../tests/editor/workbench_window.gd) · [运行器](../tests/editor/run_workbench_window.py) · [候选与实测记录](../data-collection/gonggong-ai-workbench-plan1-u06.json)

本工单的初始 Mac 实测回执记录了两处原始故障。候选的 Windows headless 结果覆盖控件焦点和选区，macOS 原生桌面焦点需以对应候选的实际运行记录为准。[会话重命名回执](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1745#issuecomment-7059220987) · [Editor Settings 回执](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1745#issuecomment-7062652835)
