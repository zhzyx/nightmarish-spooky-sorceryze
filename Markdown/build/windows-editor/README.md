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

## 内置 Terrain3D 的发行与验证

新工程可直接创建原生 Terrain3D 并在「愚公」编辑布局和生成地形场景。编辑器将区域、材质和虚拟纹理页依赖随场景导出。运行时继续读取迁移后的区域数据，并按所选渲染路径使用原生高度或虚拟高度页。

Windows 编辑器与两个导出模板都需要包含 `terrain_3d` 模块。使用同一源码工作树时依次构建三个目标，SCons 会按目标更新共享的模块注册头。用 [Terrain3D 分发工具](../../../modules/terrain_3d/tools/terrain_3d_templates.py) 检查原生类、渲染接口和编辑器 BC7 压缩器，并将调试和发行模板随便携编辑器分发。

使用无 addons 的空项目验证编辑、撤销、保存、重开和默认模板导出。旧地形迁移到新目录后，再从全新导入缓存核对原始 Region、材质纹理和已烘焙 SVT，在 Vulkan 下采集近景 RVT 和远景磁盘页的实际采样。命令见 [Terrain3D 构建、迁移与回归](../../../modules/terrain_3d/README.md)。

## 来源

- 构建入口实现：`tools/build_gonggong_editor.ps1`
- 实际构建逻辑：`tools/build_gonggong_editor.py`
