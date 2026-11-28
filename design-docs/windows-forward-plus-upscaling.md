# Windows Forward+ 时间超分辨率

在 Windows Forward+ 的 Vulkan 和 D3D12 后端接入 NVIDIA DLSS SR 和 AMD FSR 3.1.6，按视口维护历史及运动矢量。支持手动设置、Auto 选择、切换算法或调整尺寸时重置历史，以及厂商运行时缺失时可观察的回退。SDK 版本与下载校验见 `misc/scripts/upscaler_sdk.json`，使用配置见 `Markdown/build/windows-editor/README.md`。

- 在支持的 GPU 上分别运行 Vulkan 和 D3D12，核实两种厂商算法及 Auto 的实际选择。
- 核对两个视口的历史独立，检测改尺寸和切换模式后的历史重置。
- 核对缺少厂商运行库时的回退、诊断和后续帧。
- 用干净构建验证需要的运行库随 Windows 运行链可用。
- 既有编辑器曾验证双后端和回退，本轮候选完成代表性 Vulkan 源文件编译。候选的完整链接与双后端 GPU 复验分别记录。

## 交付工单

[实施工单 #2242](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/2242) · [父工单 #2240](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/2240)
