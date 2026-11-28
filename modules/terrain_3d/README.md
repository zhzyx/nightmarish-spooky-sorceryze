# Windows x86_64 Terrain3D 编辑器与导出模板

把同一源码版本构建的编辑器、调试模板和发布模板放在引擎的 `bin` 目录，三个目标均启用 Terrain3D 模块。SCons 在源码目录共享生成的模块注册文件。在同一检出中请依次完成这三个目标，也可以分别使用独立构建树。

在引擎仓库根目录运行以下命令，目标填写一个新目录。

```powershell
python modules/terrain_3d/tools/terrain_3d_templates.py E:/GodotBuilds/Terrain3D
```

分发整个目录。双击其中的 `godot.windows.editor.x86_64.exe`，打开项目，添加 Windows Desktop 导出预设，即可使用首次启动时自动发现的调试和发布模板。模板位于便携目录的 `editor_data/export_templates/<version>/`。打包工具检查三个二进制的版本、目标类型、架构、原生 Terrain3D 类和四叉树/VT 渲染接口，用编辑器实际编码一张 BC7 纹理，再分别启动两份模板的探测游戏。构建输出位于其他目录时使用 `--bin <目录>`。

## 愚公地形草案

在编辑器顶部打开 **愚公**，输入例如「东西走向的宽谷，两侧有平缓山脊」，设置宽度和起伏，点 **生成本地草案**。布局图用红色标山脊、蓝色标河谷、绿色标平地；灰度高度图按黑低白高读取。草案支持旋转、缩放、换种子和最近八个候选之间切换。

选择 **地貌参考图** 并点 **AI 解读并生成**，可以让模型根据图片和描述推断山体、谷地的位置。此操作使用本机已登录的 Codex CLI，需要时可在编辑器设置的 `yugong/codex_executable` 指定路径。草图和高度图始终在本机处理。

点 **另建地形场景** 会在项目内的 `res://yugong/` 保存独立的场景、区域数据和基础材质。场景自带总览相机与日光，可按 F6 预览。点 **应用到当前场景** 可以新建 Terrain3D，或按指定中心覆盖已有 Terrain3D 的高度。确认覆盖后可撤销、重做，也可以直接使用原生笔刷继续雕刻。新地形以世界原点为中心，首版候选使用 256 × 256 高度采样。

## 迁移旧项目

```powershell
python modules/terrain_3d/tools/terrain_3d_migrate.py E:/Projects/LegacyValley E:/Projects/NativeValley
```

用原生编辑器打开新的项目副本，等待首次导入完成。场景继续使用原有 Terrain3D 类型名。迁移工具在副本中移除旧编辑器插件的启用项及 GDExtension，保留 Region、SVT、材质、脚本 UID、导入设置和其他插件。海洋、粒子、Terrain3DObjects 等原有脚本及资源迁到 `res://terrain3d_legacy/`，UTF-8 文本资源和脚本中的显式旧路径同步改写。已有工程如果显式引用旧 `src/` 或 `menu/` 中的自定义脚本，其同目录资源一并保留。

如果二进制场景或资源保存了指向原插件脚本/资产的文件路径，或者游戏在运行时拼接旧路径，请加 `--keep-resource-paths`。这一模式在新副本内沿用旧资源目录，由引擎原生模块提供类别和工具。直接使用旧 EditorPlugin 私有 UI 接口的项目逻辑需要适配原生编辑器接口。先验证项目副本，再替换生产工作目录。

### 复验旧材质 SVT

迁移命令按字节复制 `.svt`。原先按完整输入烘焙的 v2 文件可以直接读取。有一类旧版在启用 `free_editor_textures` 时烘焙，写入的来源签名漏掉了材质贴图内容。遇到这种文件，运行时会拒绝使用并提示重新烘焙。出现该提示时，在迁移副本中选择地形，打开 Terrain3D 菜单的 **Build Material Streaming Mips…**，重新生成材质的近、远两组流，再运行冷启动飞越回归。

本山谷 Demo 使用近景 3 层、远景 5 层。也可以从引擎仓库根目录运行以下离线命令，将结果写回迁移副本。真机复验中，这对文件重烘前后仅头部偏移 80 至 87 的来源签名发生变化，所有地形材质页的内容逐字节相同。

```powershell
$terrainConsole = 'E:/GodotBuilds/Terrain3D/godot.windows.editor.x86_64.console.exe'
$migratedValley = 'E:/Projects/NativeValley'
$bakeScript = (Resolve-Path modules/terrain_3d/tests/rendering/material_rvt.gd).Path
& $terrainConsole --path $migratedValley --rendering-method forward_plus --rendering-driver vulkan --resolution 640x360 --windowed --fixed-fps 60 --disable-vsync --script $bakeScript -- --demo --bake-near-levels=3 --bake-far-levels=5 --bake-near=res://demo/data/terrain_near.svt --bake-far=res://demo/data/terrain_far.svt
```

### 复验压缩材质的缺失通道

地表资产可以缺少颜色或法线贴图。Terrain3D 为缺少颜色的层生成棋盘格，为缺少法线的层生成平面法线，使用与已导入层一致的尺寸和 mip 层数。GPU 纹理数组要求其中所有层共用格式。当一个原本压缩的数组需要占位层时，Terrain3D 将该数组的所有层解码为 RGBA8，HDR 压缩源使用半精度 RGBAH。这样发布模板只需要解码器。以 BC7 切换到 RGBA8 为例，主要 mip 的每像素显存约从 1 字节增至 4 字节。颜色和法线数组分别决定格式，输入完整的数组可以继续使用原压缩格式。

旧文件如果按旧占位层计算了来源签名，更新后可能会收到重烘提示。在迁移副本中按上一节重新生成相应材质流即可。补齐缺层或修改某一张已导入贴图同样会改变输入，已有流需要按新输入重烘。

以下夹具构建一个带 BC7 源图且有缺失通道的工程，使用编辑器烘焙，再用真实的 Windows Release 模板运行。它检查占位层、释放 CPU 侧纹理列表后的磁盘页读取，以及更改贴图内容后对旧文件的拒绝。第三个参数指定一个新测试目录。

```powershell
$terrainEditor = 'E:/GodotBuilds/Terrain3D/godot.windows.editor.x86_64.exe'
$terrainRelease = 'E:/GodotBuilds/Terrain3D/editor_data/export_templates/4.8.beta/windows_release_x86_64.exe'
python modules/terrain_3d/tests/rendering/material_svt_compatibility.py $terrainEditor $terrainRelease E:/Tests/native-svt-compat
```

## 验证全新项目导出

```powershell
python modules/terrain_3d/tools/terrain_3d_verify_export.py E:/GodotBuilds/Terrain3D/godot.windows.editor.x86_64.exe E:/Tests/native-export
```

验证工具创建不含插件的项目，使用默认 Windows 模板导出调试版和发布版，并在各自的输出目录启动。用例覆盖继承场景的高度流、近远材质流、文本资源内嵌材质、二进制资源内嵌 PackedScene，以及运行时按目录读取的 Region。三种预设分别测试选中场景、排除选中资源、自定义过滤，包括显式包含文件以及在被排除的目录中单独保留一个资源。每次导出和启动均在指定测试目录中写独立日志。

导出器根据入选场景和资源的 `height_vt_stream_file`、`data_directory`、`material_rvt_stream_file` 和 `material_rvt_far_stream_file` 收集依赖。仅由游戏脚本在运行时决定路径的文件，应加入导出预设的包含过滤器。Region 资源通过 Godot 的常规依赖收集和格式转换流程进入包体。

## 验证原生运行时、编辑器和 GPU 渲染

从引擎仓库根目录运行以下 PowerShell 命令。第一个项目没有 `addons`，会创建原生地形并检查 Region 和物理射线等运行时行为。第二个测试从空工程启动真实编辑器，创建地形、保存场景和数据，再重启编辑器检查持久化状态。编辑器测试的最后一个参数是新的输出目录。

```powershell
$terrainEditor = 'E:/GodotBuilds/Terrain3D/godot.windows.editor.x86_64.exe'
$terrainConsole = 'E:/GodotBuilds/Terrain3D/godot.windows.editor.x86_64.console.exe'
& $terrainConsole --headless --fixed-fps 60 --path modules/terrain_3d/tests/runtime
python modules/terrain_3d/editor/tests/editor_smoke.py $terrainEditor E:/Tests/native-editor-smoke
```

GPU 回归使用经过迁移的山谷 Demo。源项目应包含 `demo/Demo.tscn`、`demo/src/HeightVTPreview.gd`，以及已经烘焙的 `demo/data/terrain_near.svt`、`demo/data/terrain_far.svt`。这些项目资源由迁移工具复制；复用上面已导入的 `NativeValley` 时可以直接运行两个测试。实机运行使用 Vulkan Forward+ 窗口。

```powershell
$valleyProject = 'E:/Tests/native-gpu-valley'
python modules/terrain_3d/tools/terrain_3d_migrate.py E:/Projects/LegacyValley $valleyProject
& $terrainConsole --headless --editor --path $valleyProject --import
$detailTest = (Resolve-Path modules/terrain_3d/tests/rendering/material_rvt_detail.gd).Path
$flyoverTest = (Resolve-Path modules/terrain_3d/tests/rendering/material_rvt.gd).Path
$env:T3D_CAPTURE_DIR = 'E:/Tests/native-gpu-captures'
New-Item -ItemType Directory -Force -Path $env:T3D_CAPTURE_DIR | Out-Null
& $terrainConsole --path $valleyProject --rendering-method forward_plus --rendering-driver vulkan --resolution 640x360 --windowed --fixed-fps 60 --disable-vsync --script $detailTest
& $terrainConsole --path $valleyProject --rendering-method forward_plus --rendering-driver vulkan --resolution 640x360 --windowed --fixed-fps 60 --disable-vsync --script $flyoverTest -- --flyover
```

近景回归通过 F6/F7/F8 切换高度源、缓存材质和页来源，量化固定机位、移动和跨边界时的清晰度、误差与闪烁。飞越回归从冷缓存开始，检查近远两个磁盘 SVT 是否实际参与采样。两条命令分别输出 `Terrain close-up material regression: 0 failures` 和 `Terrain3D valley cold flyover failures=0`，并在图像目录保留实机结果。

## 愚公可玩地形验收 · 金岬荒境

在编辑器主屏打开「愚公」，输入「金色丘陵，南坡出生，西北台地上有残堡。曲折河谷从北向南，两条古道通向堡门，东线过桥，西线沿山脊」，点击「Astra 自由布局」。模型需要已登录的本机 Codex CLI。也可以点「金岬示例」直接加载内置布局。地图上的控制点可以拖动，每次松开会重新计算河床、道路和桥，并保留修改前的候选。点「生成场景并试玩」即可从出生点步行。WASD 移动、Shift 加速、Tab 切换鸟瞰、R 回到出生点。

每个新场景的目录包含原生 Terrain3D 区域、地表图层、场景用到的模型和角色，以及记录描述、布局来源、控制点、尺寸与种子的 `layout.json`。可在愚公中重新打开布局继续调整。「应用到当前场景」覆盖已有地形时只改高度。要生成河面、可碰撞桥面、地标和角色，请使用新场景入口。

从空工程运行验收。固定布局用于日常回归，增加 `--live-ai --gpu` 会实际调用模型、通过页面启动试玩，并保存布局和游戏画面。两个命令使用不同的新输出目录。

```powershell
py -3.11 modules/terrain_3d/editor/tests/yugong_playable_smoke.py $terrainEditor E:/Tests/yugong-march
py -3.11 modules/terrain_3d/editor/tests/yugong_playable_smoke.py $terrainEditor E:/Tests/yugong-march-astra --live-ai --gpu
```

用例检查南侧出生点、西北台地残堡、南北河谷和东路过桥，分别发布初次生成与拖动调整后的场景。两版都验证 1024 × 1024 高度场对应的 16 个原生区域，以及东西古道的全程角色碰撞行走。另检查候选隔离和布局重开后高度逐字节一致。角色须到达同一座台地，途中不能卡住，接地帧占比须超过 96%。

## 愚公离线制作 · 从金岬提炼的地形操作

在「愚公」输入「南坡出生，西北残堡立在高台地，曲折的宽河从北向南，东线过桥，西线沿山脊」，点「本地生成可玩地形」。金岬尺度可设为宽 1536 米、起伏 195 米。生成后拖动地图上的点，或在「当前布局整形」调参数，再点「按当前布局重新整形」和「生成场景并试玩」。试玩中按 1 返回出生点、2 查看旧渡、3 查看目标台地，Tab 可切回步行。

| 初版制作中的操作 | 愚公如何复用 |
| --- | --- |
| 先定出发方向、目标台地与轮廓，再布山脊 | 离线规则从方位和种子构造控制点；台地中心始终是两路共同的终点。 |
| 保留台地起伏，同时拉平古道和出生点 | 道路中心按限坡曲面整平，沿脊一路补出两侧山肩并在河岸收坡；出生点至目标间可保留带平滑边缘的视线走廊。 |
| 先切河床，再修过河段 | 先算河岸距离，实际相交的道路才架桥。桥面和碰撞跟随道路坡度，石拱沿弯道分段。 |
| 配合近、中、远景反复查看 | 复用泉亭、树木、残堡、远山和天空。取样河岸、比较遮挡，在有可用地点时将金树安排在桥后，并生成旧渡机位。 |
| 调河宽、改道宽、抬升台地 | 三项操作保留当前控制点，每次生成新候选。地图显示实际河宽、路宽和台地高差。 |
| 依据坡度铺岩壁、草甸与道路，减少贴图重复 | 复用金岬的斜面投影、分层去重复、近远缩放与低频颜色变化。 |

中文规则支持八个出生与目标方位、残堡／古树／石冢、南北或东西流向、东西路过桥，以及宽河、小溪、小径、高台地等描述。当前采用一河、两路、一处目标台地的布局。操作表保存在新场景目录的 `layout.json` 内，可在愚公点「载入当前场景布局」直接接着编辑。已有场景上的覆盖操作仍用于局部高度编辑，新场景入口会同时发布景观和角色。

轻量模型只需填五个字段。例如把下面一行粘贴到描述框，再点本地生成，即可制作西南出发、前往东北古树的变体。「复制轻量模型指令」会将字段说明和当前描述一并放入剪贴板。

```json
{"spawn":"SW","goal":"NE","landmark":"tree","flow":"WE","bridge":"west","operations":{"river_width":70,"road_width":75,"plateau_rise":130}}
```

`flow` 的两个字母依次表示源端和出口方位。可选的 `operations` 接受上述三个百分数（60–160）和布尔值 `sightline`。完整控制点、地形图、场景资产由本地工具生成。

```powershell
py -3.11 modules/terrain_3d/editor/tests/yugong_playable_smoke.py $terrainEditor E:/Tests/yugong-offline --offline --gpu
```

此验收使用不可用的模型程序路径，验证描述与等价意图生成相同布局、不同种子生成不同布局、整形时控制点保留，并对原版、修改版与另一份意图分别实走两条道路。窗口验证保留出生点、旧渡、堡门截图。
