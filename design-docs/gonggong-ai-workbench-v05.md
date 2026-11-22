# V05 在原视口对照资产版本

在工单详情中打开「比较本机资产候选」，选择一组已保存的人改版与候选。窗口下方的「A · 本机原件」和「B · 工单候选」在左侧原件视口中切换。状态行指明该视口正在展示哪一版。点击「退出对照」或关闭窗口即可结束。

PNG 沿用左侧纹理控件、居中位置和原件的像素尺度。候选较大时居中裁切，较小时留空。自包含 GLB 只把已解码的候选网格放进原件的 SubViewport，沿用原相机、投影、灯光和模型坐标。两个版本都能使用同类预览时才显示 A/B 控件；文件在查看期间发生变化时，下一次切换会恢复原件并提示重新保存。

对照期间暂停「选用」操作。退出时恢复之前的纹理对象或模型节点。项目元数据继续记载 E09 的路径、修订、摘要和上次显式选用的版本，重开同一项目可再次对照。

控件沿用 E09 的原生构建边界。SCons 从 `editor/docks/workbench/issue_actions/asset_candidates.gd` 生成 `IssueActions.gen.h`，由 `AIWorkbenchSidebar.cpp` 嵌入编辑器。回退可使用此前已验收的 E09 编辑器，原资产和项目元数据沿用其既有格式。

在仓库根执行 `python tests/editor/run_workbench_asset_candidates.py --same-view --godot bin/godot.windows.editor.x86_64.console.exe --report <输出文件>`。Windows 实测使用独立临时项目、正式天璇工单接口、多宝修订、PNG 与 GLB 解码器。两个后续 Godot 进程重开同一项目，检查原框位、A/B 内容、显式退出、关闭窗口和已选版本。

[原工单 #1770](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1770) · [方案一 V05](gonggong-ai-workbench-plan1.md#v05) · [候选版本与验收记录](../data-collection/gonggong-ai-workbench-plan1-v05.json)
