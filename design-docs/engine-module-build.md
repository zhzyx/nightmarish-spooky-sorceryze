# 按模块编译 Godot 引擎

从仓库根运行。使用与现有工程相同的 Python、SCons、平台和 SDK 选项。每个参与编译的 Godot 模块都提供一个 module-名称 目标，指向当前配置的模块静态库，可一次指定多个。SCons 会生成所需的头文件、构建依赖，并复用当前工作树里有效的对象。

```sh
scons module-bmp
scons module-bmp module-tga platform=windows target=editor
```

在本次验证的 macOS arm64 环境中，使用以下配置。

```sh
scons module-bmp module-tga platform=macos target=editor vulkan=no accesskit=no
```

## 按 Git 差异选择

```sh
# 预览当前工作目录相对 HEAD 的改动，含已暂存、未暂存和未跟踪文件
python3 tools/build_engine_modules.py --base HEAD

# 实际构建。将项目常用的 SCons 参数放在 -- 后面
python3 tools/build_engine_modules.py --base HEAD --build -- platform=macos vulkan=no accesskit=no

# 在干净的候选检出中，按指定基线与 HEAD 之间的全部提交构建
python3 tools/build_engine_modules.py --base origin/main --committed --build -- platform=windows target=editor
```

| 当前变更 | 自动构建行为 |
| --- | --- |
| 仅变更已列出的仓库说明、需求 Markdown 或采集记录，或没有变更 | 输出 skip，跳过 SCons，CI 保留静态检查与工单门禁 |
| 修改现有 modules 子目录内的 C、C++ 或 Objective-C 实现 | 输出 modules 预选。执行时读取当前 SCons 配置下各库的实际对象源文件，命中的库一起编译 |
| 当前平台未启用对应模块或未消费该源文件 | 转完整构建 |
| 新增、删除、移动原生文件，或涉及公共头、注册入口、测试、生成器、嵌入资源、第三方库、构建配置或未分类路径 | 转完整构建 |
| 缺失基线或无法确认构建图 | 转完整构建。归档目标的实际编译错误直接报错 |

CI 在 PR 的合并树以及普通分支推送上编译匹配的 Windows MSVC 编辑器模块。首次分支推送使用与默认分支的共同祖先。原生变动进入默认分支或合并队列时执行现有 Windows 完整矩阵，覆盖最终链接、模板、程序运行与产物。手动启动仍可运行完整构建。模块静态库可供随后链接，部署编辑器需走完整构建入口。

## 实测与来源

本机从清空构建产物的隔离检出编译 BMP，生成必要公共头、编译两个 BMP 源文件并得到归档。同配置重复构建编译动作数为零。在范围内加入 TGA 后，仅编译 TGA 的两个源文件。纯文档提交跳过 SCons，禁用 BMP、修改公共头及失去比较基线均转完整构建。直接将模块源码目录作为 SCons 目标可能在没有库时返回 up to date，应使用上述模块目标。

FreeType 和 MSDFgen 通过模块的链接输入直接提供静态库。可用 `scons module-freetype module-msdfgen` 编译。macOS arm64 复验逐项比对了当前配置的 57 个已启用模块和 57 个归档别名，两库分别包含 44 和 19 个对象。同配置再次执行时，两库均复用。使用系统预编译库的模块若无本地归档，则没有独立归档目标。

需求、独立审查和交付关联 [Issue #739](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/739)。编译边界沿用 godot-build-placement 的已验证经验，按构建消费者识别。回退时使用 SCons 默认目标和原 Windows 完整构建工作流。
