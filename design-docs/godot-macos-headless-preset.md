# macOS 编辑器启动时启用共工后台验证预设

本次 Codex 用户授权实现并合入 main。将本机已经验证的 headless 编辑器入口检查作为 Godot 宿主子模块的启动预设。macOS 打开交互式定制编辑器时自动在后台用同一编辑器、独立临时工程和编辑器配置验证 AI Chat 入口。记录成功或失败，保留正常编辑器交互。后台子进程不得递归触发。覆盖常规启动和重复启动、后台探针成功和失败、配置隔离。屏幕像素与系统焦点另行验证。目标平台为 macOS arm64；变更范围限 Godot 宿主接入、相关测试、说明和工单记录。

工单 https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/226 。构建、两次隐藏启动及失败清理记录见 `data-collection/godot-macos-headless-preset.json`（相对仓库根）。

整合并发交付 #229 后复用同一个静默验证入口与缓存协议。每次启动检查回执；本机构建或探针变化后运行 AI Chat 检查，命中时免重复启动。
