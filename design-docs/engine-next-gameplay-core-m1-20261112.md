<!-- gonggong-request:engine-next-gameplay-core-m1-20261112 -->

# Engine Next Gameplay 独立内核 M1

## 当前结论

- 用户目标：把 `GameplayPredictionInput`、`GameplayPredictionState`、`GameplayPredictionModel` 和 `GameplayInterpolationBuffer` 的内部数据与算法抽取为真正独立编译、独立测试、不链接 Godot 的 C++ 实现，而不是给 Godot 类型改名。
- 授权来源：用户先确认按文件级方案实施，随后要求按最新项目 C++ 规范落地，并于 2026-11-12 19:41 再次明确“落地吧”。
- 正式编码规范：根目录 `CPP_CODING_STANDARD.md` v1.1；语言基线为 C++17，不使用更新标准特性，不使用 `throw`、`try`、`catch`。
- 基线：经 GitHub API 回读的远程 `main` 为 `8789801187f2054c377550709c9f9900503cdd01`。两次 `git fetch` 均因 GitHub 443 连接失败未成功，但目标提交已在本地对象库且与 API 回读一致；本任务分支已快进到该精确提交。
- 需求 ID：`engine-next-gameplay-core-m1-20261112`。
- Issue：[#939](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/939)。
- 类别：`type:development`。
- 责任人：当前 Kimi Work 会话；本地验证、正式门禁、精确候选 CI、main 回读及已验收 Issue 收尾沿既有授权连续执行。

## 范围与非目标

### 范围

1. `PredictionInput`、`PredictionState` 的纯值数据语义、默认值、有限性验证和复制。
2. `PredictionModel` 的固定步长模拟、输入验证和确定错误状态。
3. `InterpolationBuffer` 的有界排序、重复时间处理、插值、末值保持和陈旧状态。
4. 原四个 Godot 类的兼容适配器、共享输入 Trace、旧实现 golden、独立测试及现有 Gameplay 回归。
5. 独立静态库与测试可执行文件、真实编译依赖和链接输入证据、Windows MSVC／macOS Clang CI。
6. `engine_next/build-impact.json`、实测构建失效和回退证据。

### 非目标

- 不迁移 `GameplayClientPrediction`、`GameplayServerPrediction`、`GameplayNetworkPrediction`、`MultiplayerPeer`。
- 不迁移 Session、World、ReplicationGraph、Relevancy、渲染器、GDScript、场景格式或编辑器。
- 不创建完整 `next_runtime` 可执行程序，不宣称整个新运行时已经完成。
- 不引入 CMake、Ninja、第三方测试框架或新的运行时依赖。
- 不长期保留旧、新两套算法；旧实现只用于实施前生成基准输出。

## 文件级设计

### 独立内核

命名空间为 `EngineNext::Gameplay`，新增文件使用 PascalCase：

```text
engine_next/
├── include/EngineNext/Gameplay/
│   ├── Status.h
│   ├── Vector3.h
│   ├── PredictionTypes.h
│   ├── PredictionModel.h
│   └── InterpolationBuffer.h
├── Gameplay/
│   ├── PredictionModel.cpp
│   └── InterpolationBuffer.cpp
├── Tests/
│   ├── TestFramework.h
│   ├── TestMain.cpp
│   └── Gameplay/
│       ├── PredictionTrace.h
│       ├── TestPredictionModel.cpp
│       ├── TestInterpolationBuffer.cpp
│       └── TestPredictionTrace.cpp
├── Tools/
│   ├── BuildGameplay.py
│   └── TestBuildGameplay.py
└── build-impact.json
```

公共类型：

- `Vector3`：三个 `float` 分量，固定单精度契约，不依赖 Godot `real_t`。
- `PredictionInput`：`sequence=0`、`movement_input={}`、`step_msec=16`。
- `PredictionState`：位置、速度、`confirmed_sequence=0`、`server_time_msec=0`。
- `Status`：`Ok`、`InvalidParameter`、`AlreadyExists`，使用明确底层类型和枚举值。
- `PredictionModel`：配置 getter／setter 与 `Simulate()`；合法操作不分配内存。
- `InterpolationBuffer`：`AddSample()`、`Sample()`、配置、计数和清理；存储有界，采样结果使用 `std::optional<PredictionState>`。
- `InterpolationStatus`：空、单样本、范围前、已插值、保持、陈旧保持，字符串只在 Godot 适配器生成。

错误通过状态返回，不使用异常。内存分配失败遵循仓库无异常构建策略，不声称可恢复。公开头直接包含所需声明，禁止 Godot 类型、宏、包含和链接输入。

### Godot 兼容适配器

新增：

```text
modules/gameplay/GameplayPredictionCore.h
modules/gameplay/GameplayPredictionCore.cpp
```

修改：

```text
modules/gameplay/gameplay_prediction.h
modules/gameplay/gameplay_prediction.cpp
modules/gameplay/SCsub
```

- 只把四个目标类移入兼容文件；原 `gameplay_prediction.h` 继续包含兼容头，保持现有 C++ 包含路径。
- 四个 Godot 类保留原类名、继承、`GDCLASS`、脚本方法、属性、默认值、字典键和状态字符串。
- 每个类持有对应内核值对象；`Vector3`、`Ref`、`Dictionary` 和 `Error` 转换只在适配器发生。
- `GameplayClientPrediction`、`GameplayServerPrediction` 和 `GameplayNetworkPrediction` 继续调用原 Godot API，不直接依赖新内核。
- `register_types.cpp`、`config.py` 和类 XML 原则上保持不变，以 doctool 核对公共 API。
- `SCsub` 显式编译两个内核实现和适配器，不将任何 Godot 文件加入独立目标。

## 固定行为语义

- 输入数据层允许默认序号零；模拟拒绝零序号、错误步长、非有限或长度超限输入。
- 最大速度必须有限且为正；固定步长为 `1–1000 ms`。
- 速度为移动输入乘最大速度，位置按模型固定步长推进；只更新确认序号，不改变服务器时间。
- 样本按服务器时间升序；同时间样本仅在确认序号更大时替换，否则返回 `AlreadyExists`。
- 缓冲容量为 `2–4096`，延迟为 `0–60000 ms`，陈旧阈值为 `1–60000 ms`。
- 保留空、单样本、范围前、插值、保持和陈旧保持的现有分支顺序；单样本仍优先返回 `single_sample`。
- 插值采用 `from + (to - from) * weight`；确认序号取后一样本，时间取目标时间。
- 末值保持不外推；陈旧判断使用严格大于阈值。
- 对极大有限值造成的结果溢出，新实现先验证完整候选状态，失败时不提交部分写入；该异常路径修正单独记录和测试，合法输入基准不得修改。

## Trace 与测试复用

- `PredictionTrace.h` 仅使用标准 C++，保存共享输入操作和旧实现生成的 golden，不包含 Godot 类型。
- 新增 `modules/gameplay/tests/TestPredictionCore.h`，由现有模块测试生成器自动发现；与独立测试使用同一 Trace。
- golden 在切换前由未修改的旧 Godot 实现生成，记录源提交、命令、输出摘要；不提交旧算法副本。
- 独立测试使用项目内极简测试入口，不链接 Godot 或 doctest。
- 现有 `test_gameplay_framework.h` 保持并运行，覆盖 Client／Server／Network 经兼容壳的间接回归。
- 覆盖默认值、复制隔离、固定步长、连续模拟、非法数值、错误步长、零序号、溢出、乱序、重复、淘汰、边界时间、清空和陈旧阈值。
- 默认单精度 Godot 与独立内核对 golden 比较浮点位模式；双精度 legacy 构建只声明近似兼容。
- 同一 Trace 在同进程重复和干净目录新进程中结果一致；Windows 与 macOS 比较规范化结果，不要求二进制字节一致。

## 独立构建与无 Godot 证据

`BuildGameplay.py` 仅使用 Python 标准库，直接驱动：

- Windows：MSVC `cl`、`lib`、`link`，C++17、`/W4 /WX /EHsc /fp:strict`。
- macOS：Clang `clang++`、`ar`，C++17、`-Wall -Wextra -Werror -ffp-contract=off`。

产物只写入 `build/engine_next/`。脚本从实际链接 response 生成清单，并保存真实编译包含、对象、静态库和测试程序摘要。CI 执行：

```text
python tools/check_engine_next_contract.py --repo . --require-sources --require-link-manifest --link-manifest <实际清单>
```

必须同时取得：直接与传递源码审计、真实编译包含审计、归档成员审计、实际链接输入及 SHA-256、平台动态依赖、无 Godot 未解析符号、干净目录运行结果。负例必须拒绝 Godot include、越界对象和伪造库。即使目标级检查通过，也不把完整 `godot_free_runtime_verified` 提前标为 true。

## 构建失效与回退

`engine_next/build-impact.json` 分类为 `native`：代码同时参与独立静态库和 legacy `module_gameplay` 原生编译，没有可替换运行包。

`data-collection/engine-next-gameplay-core-m1-build-impact-r6.json` 的 `input_blobs` 覆盖全部内核文件及实际 Godot 消费者、共享 Trace、构建脚本、契约和工作流。`checks` 至少包含：

- `native_invalidation`：临时改变真实内核输入，确认对象、库和测试程序重建，并观察探针行为变化。
- `rollback`：恢复原 blob，重建并恢复原 Trace 和行为。
- 独立测试、源码契约、链接清单、Godot 差分和现有 Gameplay 回归。

所有证据绑定精确候选 index，输入变化后重新实测。

## 性能验收

Release 下执行 100 万次固定步长模拟和容量 4096 的 5 万次混合插值操作，记录真实环境、中位数、分配特征和防优化校验和。`Simulate()` 与 `Sample()` 不分配堆内存，缓冲规模不随操作轮次无界增长。同机 base/candidate 中位数回归超过 15% 时阻断排查，不跨机器比较绝对耗时。

## PR 拆分与停止条件

### PR A：独立内核与基准

包含独立实现、测试、构建工具、契约与 CI、旧实现 characterization 测试和构建证据。此时尚不切换正式 Godot 实现。回退只需移除新增独立目标和测试，旧 Godot 行为不变。

### PR B：Godot 兼容壳

基于 PR A 合入后的最新 main，切换四个类并复用同一 golden，完成 Godot 构建、完整 Gameplay 回归和 API 核对。回退恢复 legacy 壳与 `SCsub`，独立内核可保留但不再被 Godot 消费。

两个 PR 共用本 Issue。PR A 合入不代表 M1 完成；只有 PR B 精确候选 CI、main 回读和全部验收完成后才关闭本 Issue。

## 验收清单

- [x] 新内核只使用标准 C++17，公共头无 Godot 类型、宏或包含。
- [x] 独立静态库和测试程序在 Windows MSVC、macOS Clang 实际编译、链接和运行通过。
- [x] `--require-sources` 和真实链接清单进入专用 CI，空树及伪造依赖失败。
- [x] 共享 Trace 对旧实现 golden 差分通过，合法输入结果一致，异常修正单独留证。
- [x] 四个 Godot 类脚本 API 保持兼容，现有 Gameplay 测试和 doctool 通过。
- [x] 确定性、异常输入、容量和性能验收完成，未验证事项明确保留。
- [x] `build-impact.json`、构建失效、恢复和回退证据覆盖精确候选输入。
- [x] 两个 PR 的正式门禁、提交后 Git 数据核验、精确候选 CI、main 回读及 Issue 收尾完成。


## 最终交付回执

- PR A [#970](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/970) 于 2026-11-12T15:28:54Z 合入，merge commit 为 `309a77fadc74ad9e47df42b4c2b719970b3a7cd0`。
- PR B [#983](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/983) 于 2026-11-12T16:18:26Z 合入，merge commit 为 `b720e9c582678c1e13481d5e898676218aa6c5de`。
- main 上专用 Windows／macOS 构建、静态检查和 Windows 编辑器检查全部通过；独立目标再次为 12 个用例、200131 条检查，完整 Gameplay 为 28 个用例、4835 条断言。
- 四个 Godot 类的 API 结构均与基线一致；共享 Trace、溢出事务性行为和真实 ENet 集成均通过。
- 最终验证与交付证据见 `data-collection/engine-next-gameplay-core-m1-verification-20261112-r6.json`、`data-collection/engine-next-gameplay-core-m1-build-impact-r6.json` 和 `data-collection/engine-next-gameplay-core-m1-delivery-20261112.json`。
- 完整 `next_runtime`、渲染器、脚本系统和编辑器不在 M1 范围；本单仅完成第一批真正独立的 Gameplay 内核与 Godot 兼容壳。
