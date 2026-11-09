# 调用生图能力，将godot引擎的图标和icon换成一个水墨风格的水神共工形象

<!-- gonggong-intake:daqian-direct -->

需求 ID：`daqian-direct-e7b19bb55d61d110914a`

类别：`type:development`

来源：Godot 天枢草稿 `draft_e7b19bb55d61d110914a`，GitHub 用户 ID `350401007`。

## 原始需求

调用生图能力，将godot引擎的图标和icon换成一个水墨风格的水神共工形象


## 候选构建与图标实测

马良生成的 1254×1254 原图已归档至 `data-collection/requests/daqian-direct-e7b19bb55d61d110914a/gonggong-original.png`。回读 SHA-256 为 `8be054929e9847509173f0cdad1e6c3cd5a15c3048c3d3b0537185919eb7f120`。

候选使用 `d3d12=no` 和 `angle=no` 构建。宿主返回自动重启成功，恢复回执指向该候选程序，AI 面板就绪，原会话在新进程中继续。

Windows 编辑器和控制台两个可执行文件中的 16、32、48、64、128、256 像素图层均与对应 ICO 逐字节一致。Windows Shell 分别返回 16×16 小图标，透明度至少为 32/255 的像素分别为 146 和 162。控制台资源沿用右下角终端徽标。

启动图使用原有 800×600 画布。新头像按比例缩为 142×137，置于原 144×137 区域，下方字标已逐像素比对一致。

“关于”窗口探针读到 187×69 纹理和按比例居中的显示模式，但退出时宿主清理了后台进程，该次检查未通过。各实际入口的视觉对照、最小尺寸轮廓辨识度及各档裁切仍待验收。

## 简化图标与水墨启动图

用户选定尺寸对照图下排的透明简化稿，红发与蓝色水纹用于当前 Windows 编辑器的小图标。原 800×600 水墨启动图沿用提交 2d2f800f 的文件。项目管理器标题、关于窗口、帮助菜单、文件列表与缩略图、默认项目图标、应用窗口、Windows 编辑器与控制台均在本次范围内。使用自定义图标的项目继续读取各自的资源。

本次候选的主题纹理在后台从编译后的编辑器读取，六种纹理与相同尺寸的源 SVG 渲染逐像素一致。通过帮助菜单打开关于窗口，检测到可见的 187×69 字标纹理按比例居中。项目管理器后台启动后读到可见的 100×24 标题按钮纹理。Windows 两个 EXE 中 16、24、32、48、64、128、256 像素的图层全部逐字节匹配相应 ICO。编辑器嵌入的启动 PNG 与原水墨启动 PNG 字节一致。

本次结果见仓库根相对路径 `data-collection/requests/daqian-direct-e7b19bb55d61d110914a/simplified-icon-validation.json` 和同目录的 `simplified-editor-icons.png`。上节以及 boot-window.png、project-manager-title.png 和 windows-icon-comparison.png 记录原水墨版本的构建。
