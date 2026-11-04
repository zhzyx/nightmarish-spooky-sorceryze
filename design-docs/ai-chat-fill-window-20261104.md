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
