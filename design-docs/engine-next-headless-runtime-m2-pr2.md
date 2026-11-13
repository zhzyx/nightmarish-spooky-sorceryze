# M2 PR2：纯净 ENet 与双客户端连接出生

## 范围

- 引入上游 ENet v1.3.18（`2662c0de09e36f2a2030ccc2c528a3e4c9e8138a`）及 MIT 许可证，不使用 Godot socket 或 MultiplayerPeer 封装。
- 新增 32 字节 `NEXT` little-endian 帧头、版本／长度／序号／SessionId 校验及 hello、welcome、disconnect、error 编解码。
- 新增独立 ITransport、实际 PeerId 映射、SessionManager 和服务器 World 实体分配。
- `next_server` 与两个独立 `next_client` 以真实 UDP 完成连接和出生；重连字段存在但本切片明确拒绝，不宣称恢复成功。
- 上游仅以 `offsetof` 修复三处空指针成员访问 UB，其他源码保持原样；C 与 C++ 分语言模式编译，对象名带路径摘要，静态库精确重建。

## 实际验证

- macOS arm64／Clang：8 个运行时测试、116 条检查通过。
- 一服两客户端真实 UDP：两组不同 SessionId／EntityId、不同 PeerId，客户端与服务器记录一一对应，所有进程退出码为 0 且 stderr 为空。
- 构建目录、复制后的干净运行目录及 77 文件无 Godot 源码树均完成相同握手。
- 三份源码＋真实链接契约通过；服务器／客户端各 22 个对象和 1 个静态库，测试 27 个对象和 1 个静态库。
- ASan／UBSan 下同一握手通过；M1 为 16 个用例、200161 条检查通过，Trace 保持 `f55d1f5bc85bb72376d3f31cdf9b64aac91e714b6556dbce1663c1db7995924c`。
- 原生失效：默认 tick 从 1 改为 2 后 native key 从 `7b334b32eed0ebc1dc543ab33fe3aa3842d97d775f8f30c51bba11188556a7d7` 变为 `56b0f1e1811203deeda1c7013892ca6e939116fc6e29f72f6760e8933ab02baa`，实际启动同步变化；恢复后键和行为恢复。
- 构建工具测试 11 项、契约测试 23 项通过；Ruff 0.17.1 与 codespell 2.4.2（仅第一方路径）通过。

证据：`data-collection/engine-next-headless-runtime-m2-pr2-verification.json` 和 `data-collection/engine-next-headless-runtime-m2-pr2-build-impact.json`。

## 未验证与后续

- Windows MSVC 和 Linux x86_64 仍需精确候选 CI 实测，不能由 macOS 结果替代。
- 本切片不包含权威移动、客户端预测、远端插值、重连或 10,000 tick 长稳；#1042 保持开放并继续第三片。

## R1 Windows 与格式修正

- PR #1056 的 macOS 与 codespell 已通过；Windows 在上游 `compress.c` 的 C4245 处失败，另有 clang-format／Ruff 格式差异。
- 仅对上游 C 编译单元增加 `/wd4245`，第一方 C++ 保持警告即错误；以 clang-format 18.1.8 和 Ruff 0.17.1 处理第一方文件，没有重写上游源码。
- 修正后重新完成本机 8 个测试、116 条检查、三份契约、Sanitizer、真实 UDP 握手和 78 文件干净源码树验收。
- R1 证据采用追加文件，不修改 PR #1056 的原始回执；新精确候选的 Windows、macOS 和静态 CI 仍须重新回读。

## R2 MSVC 与 clang-format 版本修正

- PR #1058 的 Windows 继续在上游 `host.c` 的 C5287 处失败；静态检查实际使用 clang-format 22.1.5。
- 仅对上游 C 编译单元增加 `/wd5287`，并按 CI 的 clang-format 22.1.5 处理第一方文件，不改变告警策略或上游实现。
- 本机运行时测试、三份契约、Sanitizer、真实 UDP 握手和 78 文件干净源码树再次通过。
- R2 继续采用追加证据，新精确候选的 Windows、macOS 和静态 CI 必须重新回读。

## R3 Winsock 弃用 API 修正

- PR #1062 的静态检查和 macOS 已通过，Windows 剩余 `win32.c` 的 C4996：`gethostbyname`／`gethostbyaddr` 弃用告警。
- 按 MSVC 提示，仅为上游 ENet 的 C 编译单元定义 `_WINSOCK_DEPRECATED_NO_WARNINGS`，不全局关闭弃用告警，也不改变上游网络实现。
- 本机运行时测试、三份契约、Sanitizer、真实 UDP 握手和 78 文件干净源码树再次通过。
- R3 继续追加证据，新精确候选的 Windows、macOS 和静态 CI 必须重新回读。
