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

## 安装与启动

```powershell
./tools/install_gonggong_editor.ps1
./tools/launch_gonggong_editor.ps1
```

安装、启动会操作实际应用或进程；执行前确认目标和任务授权，不替换其他任务正在使用的应用。

## 来源

- 构建入口实现：`tools/build_gonggong_editor.ps1`
- 实际构建逻辑：`tools/build_gonggong_editor.py`
