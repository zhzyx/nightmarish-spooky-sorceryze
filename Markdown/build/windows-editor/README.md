# Windows 编辑器构建

以下入口适用于当前仓库；在其他工作副本执行前，先确认脚本及参数存在且一致。

## 编译

```powershell
./tools/build_gonggong_editor.ps1 -Python PATH/TO/python.exe
```

脚本将指定 Python 传给 `tools/build_gonggong_editor.py`，失败时包含编辑器构建或 AIChat 回归失败。可选参数：

- `-Jobs 8`：并行任务数，范围 1–1024。
- `-UseMinGW`：改用 MinGW。
- `-CachePath PATH`：指定构建缓存目录。
- `-CacheLimitGiB 8`：缓存上限，范围 1–65536 GiB。

## Windows x64 时序超分

Forward+ 视口可独立选择时序超分，重建历史随视口尺寸、模式和相机历史重置。Vulkan 与 D3D12 共享视口接口。驱动、设备或运行库不满足条件时，渲染器选择可用的回退路径，并通过视口 API 报告结果。

MSVC 构建时可在编译前运行 `py -3.11 misc/scripts/fetch_upscaler_sdk.py`。脚本按锁定清单校验 NGX 和 FidelityFX SDK，将头文件、静态库放入本地缓存，并将运行库和厂商说明放入 `bin`。SDK 构建需要启用 Vulkan，可按现有流程另行启用 D3D12。在导出目录运行游戏时，使用同一工作树构建的模板，再运行 `py -3.11 misc/scripts/fetch_upscaler_sdk.py --runtime-dir <游戏可执行文件目录>`。

Forward+ 项目可在 `rendering/scaling_3d/mode` 选择 DLSS SR、AMD FSR 或 Auto，或通过 `Viewport.scaling_3d_mode` 为每个视口设置。将 `scaling_3d_scale` 设置为约 0.667 即可按每轴三分之二渲染。在绘制后读取 `Viewport.get_upscaling_info()` 获取实际算法及回退原因。

## 安装与启动

```powershell
./tools/install_gonggong_editor.ps1
./tools/launch_gonggong_editor.ps1
```

安装、启动会操作实际应用或进程；执行前确认目标和任务授权，不替换其他任务正在使用的应用。

## 来源

- 构建入口实现：`tools/build_gonggong_editor.ps1`
- 实际构建逻辑：`tools/build_gonggong_editor.py`
