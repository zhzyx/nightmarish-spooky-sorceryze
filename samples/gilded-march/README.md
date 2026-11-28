# 金岬荒境 · The Gilded March

原创地形示例。工程使用原生 Terrain3D，包含南肩废泉亭、西北台地的风冠残堡、玉灰河及两条古道。地形由 16 个区域组成，可在编辑器中继续雕刻。布局源文件和创作记录位于 [design](design)。

在 Windows 构建同一工作树的编辑器后，双击「游览金岬荒境.cmd」试玩，或双击「编辑地形.cmd」打开场景。也可以从已构建的编辑器中导入本目录的 `project.godot`，打开 `March.tscn`。构建与运行库准备见 [Windows 编辑器构建](../../Markdown/build/windows-editor/README.md)。

按 1 至 4 切换南肩、鸟瞰、旧渡和堡门。Tab 切换步行，WASD 行走，Shift 加速，H 隐藏提示，Esc 释放鼠标或退出。

工程默认使用 Forward+、1440×810 和约三分之二内部渲染尺寸。时序超分模式默认为 Auto。运行时可在视口通过 `get_upscaling_info()` 读取实际算法及回退原因。

第三方素材来源见 [地表纹理](materials/CREDITS.txt)、[废泉亭](world/springhouse/CREDITS.txt) 和 [天空摄影](design/创作说明.txt)。
