# 马良离线桌面发行包

父工单 #611 要求 Mac 和 Windows 安装包包含 Hunyuan3D 模型及运行环境。本项负责发行构建和 Windows 发行包验收。构建时组装各平台可迁移的 Python、ComfyUI、模型、依赖及其分发声明。终端用户直接打开打包的编辑器即可用已有图片生成网格。

接受打包好的 Mac 编辑器或原生可执行文件以及 Windows 编辑器发行目录。Mac 资源目录为 `Contents/Resources/maliang-hunyuan`，Windows 资源目录为编辑器同级的 `maliang-hunyuan`。真实提交物需验证模型完整性、平台运行环境、移动后启动，以及脱离主机构建路径仍能产生非空网格。保留各平台实际验收边界。

[父工单 #611](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/611) 的编辑器负责自动连接，两个平台均使用发行版内的解释器。Windows 检查在同一份空白用户配置中首次连接、关闭服务、移动发行目录，再断开外网运行图生网格、发布和重开场景。流程和平台源清单见[发行构建说明](../tools/maliang_hunyuan/README.md)。
