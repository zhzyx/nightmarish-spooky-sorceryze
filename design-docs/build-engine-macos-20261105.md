# 编辑器 build_engine 自更新支持 macOS/Linux

<!-- gonggong-request:build-engine-macos-20261105 -->

- 需求 ID：`build-engine-macos-20261105`
- 类别：`type:bug`
- 关联：Issue #58 会话暴露

## 问题

编辑器 AI Chat 的「编译并更新引擎」宿主动作 `build_engine`（side-by-side 自更新）在 macOS 上无法工作，导致依赖该动作的 C++ 改动无法在编辑器内编译验证，Agent 空转。

根因是两处 Windows 硬编码：

1. `tools/editor_self_build.py`：
   - `build_options()` 对非 Windows 平台直接抛异常 "Side-by-side self-update currently supports Windows editors"；
   - `artifact_path()` 产物名写死 `godot.windows.editor` 与 `.exe` 后缀。
2. `editor/docks/ai_chat_dock.cpp`：
   - `_poll_engine_build()` 成功判定写死 `godot.windows.editor.` 前缀；
   - 构造函数 `ai_chat/build_python` 默认值写死 `.venv/Scripts/python.exe`（Windows venv 布局），macOS/Linux 为 `.venv/bin/python`。

## 修复

- `editor_self_build.py`：platform 白名单 `{windows, macos, linuxbsd}`；产物名按平台生成，仅 Windows 加 `.exe` 后缀。
- `ai_chat_dock.cpp`：成功判定改为 `begins_with("godot.") && contains(".editor.")`；`build_python` 默认值按 `WINDOWS_ENABLED` 宏分支。

## 验证

- Python 语法检查通过；三平台产物名解析实测正确。
- macOS x86_64 增量编译通过（EXIT=0），产物覆盖 `bin/godot.macos.editor.x86_64`。
