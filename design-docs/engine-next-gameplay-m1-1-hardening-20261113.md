<!-- gonggong-request:engine-next-gameplay-m1-1-hardening-20261113 -->

# Engine Next Gameplay M1.1 收尾加固

## 当前结论与授权

- 用户附件要求：在不改变 M1 正常行为的前提下，补齐插值极端数值保护和完整 legacy 回退证据，不启动 M2。
- M1 已由 PR #970、#983、#987 合入；本次基线为最新远程 `main@ad79c25d9cdae8a635fdf74ff957336799903a10`，保留其他并发交付。
- 需求 ID：`engine-next-gameplay-m1-1-hardening-20261113`。
- Issue：[#1025](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1025)，不重开已完成的 #939。
- 类别：`type:development`。
- 责任人：当前 Kimi Work 会话，按既有授权连续完成验证、正式门禁、精确候选 CI、main 回读和 Issue 收尾。
- 编码规范：`CPP_CODING_STANDARD.md` v1.1，C++17，无 `throw`、`try`、`catch`，不批量格式化旧文件。

## 文件级实施

### 1. 插值极端数值保护

- `engine_next/include/EngineNext/Gameplay/Vector3.h`
  - 新增 `TryLerp` 成功返回值和输出参数。
  - 仅当浮点中间值或结果出现 NaN/Inf 时进入 double 修复路径；快速路径的浮点位模式不得改变。
  - double 计算转回 float 后仍非有限时返回 `false`，不写入部分结果。
- `engine_next/Gameplay/InterpolationBuffer.cpp`
  - 在插值位置或速度任一失败时返回明确的 `numeric_error` 和不存在的 `state`，不改变既有六种状态。
- `modules/gameplay/adapters/GameplayPredictionCore.cpp`
  - 将新状态映射为 `numeric_error`，`sample()` 签名不变，失败时 Dictionary 不含 `state`。
- `modules/gameplay/doc_classes/GameplayInterpolationBuffer.xml`
  - 记录 `numeric_error` 的含义和空 `state` 语义，其他状态与签名不变。

### 2. 双端测试

- `engine_next/Tests/Gameplay/TestInterpolationBuffer.cpp`
  - 覆盖 `-FLT_MAX` 到 `FLT_MAX` 的 0.5 插值、位置与速度分别差值溢出、最终加法溢出、double 修复后超出 float 范围的明确失败、普通 golden 不变、失败无部分提交和 uint64 极大时间值。
- `modules/gameplay/tests/TestPredictionCore.h`
  - 验证 Godot 对极端有限位置与速度样本返回有限的插值结果，以及普通 golden 不变。
  - `[0,1]` 权重下，有限端点经 double 总能得到有限结果，因此 `numeric_error` 是防御性分支；越界失败由直接 `TryLerp` 测试覆盖，不伪造 Godot 错误样本。
- `engine_next/Tests/Gameplay/PredictionTrace.h`
  - 仅在确有需要时调整，默认不改变既有 golden。
- Windows MSVC、macOS Clang、ASan/UBSan 均覆盖新增路径；同机中位数性能回归门槛为 15%，不普遍 double 化。

### 3. 完整 legacy 回退与恢复

在隔离工作树执行：

1. 保存 M1.1 候选四个类、适配器、SCsub、engine_next 的精确 blob 和补丁。
2. 临时恢复 PR A 合并提交 `309a77fa` 对应的 `gameplay_prediction.h/.cpp`、`SCsub` 及同期测试版本；适配器可保留但不参与 legacy 构建，独立 engine_next 不参与 legacy 使用证明。
3. 实际重建 Godot，记录 legacy 消费者、产物 SHA-256、共享 golden、目标测试和完整 Gameplay 回归。
4. 恢复 M1.1 候选，重新构建并重复相同测试，记录恢复后的消费者、产物摘要和工作区状态。
5. `build-impact` 分别记录原生输入失效、完整 legacy 回退、恢复 M1.1 三项证据，不再把 8→9→8 单独描述为完整 legacy 回退。

## 验收边界

- 独立构建、真实链接清单、`--require-sources` 和 `--require-link-manifest` 通过。
- 独立测试、构建工具测试、完整 Gameplay、doctool/API 结构核对通过。
- 新插值路径在 Windows 和 macOS CI 均有实测，正常 golden、错误语义和性能没有未解释变化。
- legacy 与 M1.1 两个方向均有真实文件 blob、消费者、产物摘要和回归结果。
- `godot_free_runtime_verified` 继续保持 `false`，不扩大声明。

## 不做

- 不启动 M2、完整 next_runtime 或动态库热更。
- 不迁移 Client/Server/Network Prediction、Session、World、渲染器、脚本或编辑器。
- 不处理双精度 Godot 的逐位一致。
- 不批量格式化旧文件，不混入版权头调整。

## 验收清单

- [x] 极端有限输入在 float 快速路径失败时进入 double 修复，失败明确返回 `numeric_error` 且无 `state`。
- [x] 正常 golden 位模式不变，失败无部分更新，时间和性能边界通过。
- [x] legacy 与 M1.1 两方向真实重建、消费者、产物和回归证据完整。
- [x] 独立构建、完整回归、API、双平台 CI、正式门禁和 main 回读完成，交付证据与 Issue 收尾完成。

## 主线交付回执

- PR [#1028](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/1028) 于 2026-11-13T05:05:34Z 合入，merge commit 为 `d5a77b1d539a9b92a1b81fc84c4df447dab82a7d`；签发 head 为 `5f4362e373ca23ca7277bf0e56ef43c378caa713`。
- 候选与 main 的 Windows MSVC、macOS Clang、静态检查和 Windows 编辑器检查全部通过；独立目标为 16 个用例、200161 条检查，完整 Gameplay 为 29 个用例、4846 条断言。
- 正常 Trace 摘要保持 `f55d1f5bc85bb72376d3f31cdf9b64aac91e714b6556dbce1663c1db7995924c`；极端有限位置与速度得到有限插值，无法表示的结果明确返回 `numeric_error` 且不包含 `state`。
- 完整 legacy 回退排除了全部 `engine_next` 和适配器消费者，恢复 M1.1 后重新包含两个内核实现和适配器；恢复后的编辑器 SHA-256 与回退前完全一致。
- 最终验证、构建边界和交付证据分别见 `data-collection/engine-next-gameplay-m1-1-hardening-verification-20261113-r8.json`、`data-collection/engine-next-gameplay-m1-1-hardening-build-impact-r7.json` 和 `data-collection/engine-next-gameplay-m1-1-hardening-delivery-20261113.json`。
- 本次收尾候选只追加设计完成状态、交付回执和 `request_end`，不改变已验收实现，不启动 M2。
