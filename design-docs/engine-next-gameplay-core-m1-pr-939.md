# Engine Next Gameplay M1 PR A：独立内核与构建契约

## 范围

- 新增 `EngineNext::Gameplay` 纯 C++17 数据、固定步长模型和有界插值缓冲，公共头不包含 Godot 类型或宏。
- 新增独立静态库、测试程序、公开头自包含检查、ASan／UBSan 入口和确定性 Trace。
- 新增实际编译／归档／链接 response／动态依赖／符号／干净目录审计，以及真实链接清单。
- 契约检查器支持已声明 `public_header_roots` 和安全的相对包含，继续拒绝 Godot 包含、路径逃逸、禁止 token 和伪造链接输入。
- 专用 CI 在 Windows MSVC 与 macOS Clang 构建并运行独立目标，强制 `--require-sources` 和链接清单。
- 新增旧 Godot 实现的共享 golden 和性能基线；本 PR 不切换四个生产 Godot 类，不在本 PR 宣称 M1 全部完成。

## 非目标

不迁移 Client／Server／Network Prediction、MultiplayerPeer、Session、World、Replication、渲染器、GDScript、场景或编辑器；不创建完整 `next_runtime`，不引入第三方运行时或平行维护旧、新两套算法。

## 编码规范

新增代码遵循 `CPP_CODING_STANDARD.md` v1.1：C++17、PascalCase 文件／类型／函数、变量类型前缀、大括号另起一行、显式类型、状态返回且不使用异常。

## 已完成的本地验证

- macOS 15.3.1 arm64，Apple Clang 17.0.0：12 个独立用例、200131 条检查通过；公开头独立编译通过。
- ASan＋UBSan：相同检查全部通过；干净目录与构建目录 Trace SHA-256 均为 `f55d1f5bc85bb72376d3f31cdf9b64aac91e714b6556dbce1663c1db7995924c`。
- 契约工具 22 项测试、构建工具 7 项测试通过；真实目标为 `sources_passed＋link_passed`。
- 旧 Godot 编辑器实际构建成功，shared golden 和性能基线共 2 个用例、19 条断言通过。
- 原生输入变化与回退实验通过：原生键、库、程序和 checksum 随真实输入变化，恢复后测试和 Trace 回到基线。
- 性能实测：旧 Godot 模型／插值中位 10931／250816 µs，最终独立 Release 为 4935／169291 µs，checksum 一致；deque 消除了满容量淘汰时的完整数组搬运。
- Ruff 0.17.1 lint／format、clang-format 18.1.8、CODEOWNERS 和包含路径校验均已在本地通过。
- 新增模块 `build-impact` 门禁和完整正式工单门禁通过。

详细证据见 `data-collection/engine-next-gameplay-core-m1-verification-20261112-r4.json` 与 `data-collection/engine-next-gameplay-core-m1-build-impact-r4.json`；初版、R2 和 R3 回执保持不变。

## 待远端与后续验收

- Windows MSVC 由本 PR 的专用 `windows-latest` 作业实际验证，本地未宣称通过。
- 两个平台的精确候选 CI、main 回读在取得真实回执后记录。
- PR B 才切换四个 Godot 兼容壳，并复用本 PR 的相同 golden 完成差分与完整 Gameplay 回归。
- 初始候选的静态检查曾发现归属、包含和格式问题，已逐项修复并复验；更新后的精确候选 CI 与 main 回读单独记录。
