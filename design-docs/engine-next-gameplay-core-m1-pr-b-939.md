# Engine Next Gameplay M1 PR B：Godot 兼容壳切换

## 范围

- 基于 PR #970 合入后的 `main@309a77fa`，将 `GameplayPredictionInput`、`GameplayPredictionState`、`GameplayPredictionModel`、`GameplayInterpolationBuffer` 的内部存储与算法切换到 `EngineNext::Gameplay`。
- 新增 `modules/gameplay/adapters/GameplayPredictionCore.h/.cpp`，保留原类名、继承关系、GDCLASS、脚本方法、属性、字典键和状态字符串。
- `gameplay_prediction.h` 继续包含兼容头；Client／Server／Network Prediction 仍只调用原 Godot API。
- `SCsub` 显式编译两个独立内核实现和兼容适配器；独立目标不包含任何 Godot 文件。
- 公共头使用仓库相对包含路径，使模块测试与独立构建都能直接解析。
- `GetCoreInput()` 与 `GetMutableCoreState()` 仅用于原生适配，避免每次模拟和采样重复转换；不增加脚本 API。

## 差分与异常行为

- 使用 PR A 已合入的相同 `PredictionTrace.h` 和 golden，不维护第二套旧算法。
- 合法输入保持位置、速度、序号、时间和状态一致。
- 极大有限值导致结果溢出时返回 `ERR_INVALID_PARAMETER`，位置、速度和确认序号均不发生部分写入。
- 空缓冲、单样本、范围前、插值、末值保持和陈旧保持语义不变。

## 已完成验证

- macOS 15.3.1 arm64、Apple Clang 17.0.0：独立 12 个用例、200131 条检查通过，`sources_passed＋link_passed`。
- Godot 完整 Gameplay 回归：28 个用例、4835 条断言通过，包含 shared golden、溢出回归和真实 ENet 集成。
- 四个类的 API 结构全部与 `main` 一致；`make_rst.py --dry-run` 无 XML warning/error，282 个既有 code-sample parity 诊断不属于本候选。
- 模块输入清单确认 `module_gameplay` 编译两个内核实现和 `adapters/GameplayPredictionCore.cpp`。
- 最终原生失效实验：默认速度 8→9 时 Godot 重建适配器并改变模型 checksum，恢复后回到 3325757522，完整 Gameplay 再次通过。
- 性能：旧实现模型／插值中位 10931／250816 µs，新 Godot 实现为 5946／177944 µs；独立 Release 为 4907／164486 µs，checksum 一致。
- Ruff、clang-format、CODEOWNERS、include 校验和 codespell 均通过。

## 待远端验收

- PR B 的 Windows MSVC、macOS Clang 专用构建、完整引擎 CI 和 main 回读在取得真实结果后记录。
- PR A 已在 #970 通过双平台专用检查、静态检查、Issue 关联和 Windows 编辑器完整构建，并合入 `309a77fa`。
- 完整 `next_runtime`、渲染器、脚本和编辑器仍不属于 M1；`godot_free_runtime_verified` 不被提前标记完成。

详细证据见 `data-collection/engine-next-gameplay-core-m1-verification-20261112-r6.json` 与 `data-collection/engine-next-gameplay-core-m1-build-impact-r6.json`。
