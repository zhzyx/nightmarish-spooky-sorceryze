# M2 PR1：独立构建与固定 tick 运行时

## 范围

- 新增标准 C++17 Clock、FixedStepLoop、World、RuntimeConfig、RuntimeHost 和 JSON Lines Trace。
- 新增真实 `next_server`、`next_client` 与 `EngineNextRuntimeTests` 可执行目标，支持手动固定 tick、确定性 Trace 和显式生命周期。
- 新增独立构建器、干净源码树导出器、三份真实 linker response／清单和 CI 命令。
- 源码契约补齐 C++17 标准头 `<charconv>`，不放宽任何 Godot 禁止边界。
- 本 PR 不包含 ENet、协议、会话、预测网络闭环或完整 M2 声明。

## 实际验证

- macOS arm64／Clang：5 个运行时测试、74 条检查通过；服务器和客户端各推进 4 tick，构建目录与干净目录 Trace 一致。
- 三份源码＋真实链接清单均通过；服务器／客户端各 9 个对象和 1 个静态库，测试 13 个对象和 1 个静态库。
- 物理无 Godot 的 43 文件源码树重新构建并运行通过，服务器和客户端契约均通过。
- M1 回归：16 个用例、200161 条检查通过，Trace 保持 `f55d1f5bc85bb72376d3f31cdf9b64aac91e714b6556dbce1663c1db7995924c`。
- ASan／UBSan：同一组运行时测试、服务器、客户端和 Trace 全部通过。
- 原生失效：默认 tick 从 1 改为 2 后 native key 从 `6e51d895b7cce7918bfe6c910591ea22ffb05fb8186e43a819534cace912d505` 变为 `8d4ef7898efd7b3d9fba745a2acf8b64515e32325c17eb97f79971b468dd1b0b`，实际启动从 1 tick 变为 2 tick；恢复后键和行为恢复。
- 构建工具测试 11 项、契约测试 22 项通过。

详细证据：`data-collection/engine-next-headless-runtime-m2-pr1-verification.json` 和 `data-collection/engine-next-headless-runtime-m2-pr1-build-impact.json`。

## 审查与未验证项

- 独立审查由源码契约、真实链接输入、平台符号／动态依赖工具、干净源码树构建及精确候选 CI 承担；没有声称额外人工独立审查。
- Windows MSVC 和 Linux x86_64 尚未在本机执行，只接受后续真实 CI 结果，不预填通过。
- 本 PR 合入只完成 M2 五个纵向切片中的第一片；#1042 保持开放，继续连接与出生切片。
