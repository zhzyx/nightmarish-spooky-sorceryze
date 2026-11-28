# 原生地形、Windows 超分辨率和金岬荒境

将原生地形编辑和渲染、Windows Forward+ 时间超分辨率及原创可玩示例交付到引擎仓库。三个子项各自走提交、验证和评审，示例用于验证引擎能力可以在仓库内复用。

| 子项 | 设计和验收 |
| --- | --- |
| [原生 Terrain3D、愚公和地形虚拟纹理 #2241](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/2241) | [原生地形设计](native-terrain3d-vt.md) |
| [Windows Forward+ DLSS SR 和 AMD FSR #2242](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/2242) | [Windows 超分辨率设计](windows-forward-plus-upscaling.md) |
| [金岬荒境可玩示例 #2243](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/2243) | [示例设计](gilded-march-playable-sample.md) |

整体验收使用同一引擎版本的 Windows 编辑器和导出模板。记录脚本、场景和旧地形数据兼容验证，核对 Vulkan 与 D3D12 的真实 GPU 验证，并从新缓存导入和运行仓库示例。验收时分别核对三个子项的提交、验证证据及原生父子工单关系。
