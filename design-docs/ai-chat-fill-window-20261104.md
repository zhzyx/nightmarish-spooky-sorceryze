# 选中 AI Chat 时占满编辑器窗口

<!-- gonggong-request:ai-chat-fill-window-20261104 -->

- 需求 ID：`ai-chat-fill-window-20261104`
- Issue：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/52
- 类别：`type:development`
- 责任人：待实际指定

## 原始需求与目标

原始需求：“aichat 现在布局是在中间。我想选择 AIChat 的时候，AIChat 窗口是占满整个窗口。”

目标：选中顶部 `AI Chat` 主屏幕标签时，AI Chat 占满标题栏以下的全部区域；切换到其他主屏幕后恢复原布局。

## 范围与非目标

范围：

- 选中 AI Chat 时隐藏左右及底部 Dock、场景标签栏和底部面板；切走时恢复，并保持无干扰模式原有状态。
- 隐藏期间保存布局不覆盖 Dock 分割位置；重启恢复到 AI Chat、切换布局时行为一致。
- 受影响模块：`editor/editor_main_screen.*`、`editor/docks/editor_dock_manager.cpp`、`editor/gui/editor_bottom_panel.*`、`tests/editor/ai_chat_integration.gd`。

非目标：保留顶部标题栏（菜单、主屏幕标签、运行栏），它是切回其他主屏幕的入口，不做隐藏；不做系统级全屏；不改 AI Chat 内部布局；其他主屏幕行为不变。

目标平台：macOS x86_64（Apple Clang 14）编辑器构建；不扩展到其他平台与导出模板。

## 验收标准

- [ ] 选中 AI Chat 时左右及底部 Dock、场景标签栏、底部面板均不可见，AI Chat 宽度等于窗口内容宽度。
- [ ] 切换到 2D/3D/Script 等主屏幕时上述区域恢复，分割位置不变。
- [ ] 进入 AI Chat 前已开启的无干扰模式在离开后仍保持开启。
- [ ] 底部面板处于展开状态时选中 AI Chat 不会出现空白主屏幕。

## 验证与采集证据

- 构建：`python -m SCons platform=macos target=editor use_volk=yes accesskit=no allow_unsupported_apple_clang=yes -j4` 通过并链接。
- headless 编辑器脚本验证：选中 AI Chat 时主屏幕宽度 279 → 587（侧边 Dock 折叠），底部面板与场景标签均隐藏；切回 3D 后宽度 587 → 279、底部面板与场景标签恢复。
- 修复了工作树中 `ai_chat_gonggong.cpp` 三处既有语法错误（`U"…" + String` 左操作数、多余右括号），否则无法链接；属 Issue #47 在途工作的阻断项。
- 谛听事件：`gonggong-diting-data/events/gonggong-workspace/ai-chat-fill-window-20261104/`。

## 2026-11-05 Windows 补充验收

本次仅交付独立验收脚本、运行证据和文档，基于 `1b0a33fd5e3a579e70c46aedeb67dc3f179c2130`，不修改引擎实现。原目标仍为 macOS x86_64；本机没有该平台运行环境，因此四项原平台验收仍保留未核销，Issue 不关闭。必要检查为独立项目 headless editor 三进程测试、正式 Issue 门禁和提交后 Diting Git 检查；不重建引擎、不切换安装。

复用 #58 的临时项目/正常退出 driver 方法。Windows editor 实测版本 `4.8.beta.custom_build.1b0a33fd5`，binary SHA-256 为 `9c60fdc6d657fbb16b4c2635b15ca58846aa822020de7ae13e864eeec90a94a0`。测试使用副本与隔离 APPDATA/LOCALAPPDATA/XDG 路径，未访问用户旧项目或聊天队列；临时路径均以运行脚本解析出的仓库根为基准。报告路径同样相对仓库根。

复现命令：`python tests/editor/run_issue52_layout_validation.py --godot <该版本的 editor 可执行文件> --report data-collection/issue52-windows-layout.json`。

实际结果见 [运行报告](../data-collection/issue52-windows-layout.json)：

- 固定 1600×1000 headless 窗口；3D 主区宽 1226，AI Chat 主区宽 1592。AI Chat 隐藏底部面板和场景标签；本轮未做像素截图，也未独立断言全部侧 Dock 不可见及内容区宽度严格相等，因此第一项仍不据此完全核销。
- AI Chat 切到 2D、3D、Script 时底部面板和场景标签恢复，Dock 分割位置逐个精确相等，宽度收回。
- 3D 中开启无干扰模式，进入 AI Chat 后返回 3D，模式仍开启。
- 先选中底部面板并按其真实展开按钮展开，确认主屏被隐藏；选 AI Chat 后展开状态清除，主屏与 AI Chat 在树中可见且宽高均非零。
- 三进程依次保存正常布局、在 AI Chat 下正常退出、重启并切回；八项已保存 Dock 分割值与正常基线完全一致，恢复宽度仍为 1226。底部面板被选中后恢复主区高度从 872 变成 645，这是打开面板占用空间，测试不将高度等同于 Dock 分割位置。

测试开发中，默认小 headless 窗口切换主屏出现最小尺寸夹限（DockHSplitMain 189→185），因此固定较宽窗口以验证原分割值恢复；窄窗口行为由 #56 负责。首次脚本还比较了所有内部 SplitContainer、把面板打开后的高度当成恢复宽度比较；已收敛为 Dock 分割值和宽度。该说明保留失败原因，不将这些早期运行宣称为通过。Windows 补充三项均通过后停止扩展；runner 当前仅允许 Windows；macOS 环境可用后须先适配原生配置目录隔离，再做目标平台核验。
