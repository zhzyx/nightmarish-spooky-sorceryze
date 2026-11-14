# M2 PR5：独立运行时长稳、发布包与最终兼容验收

## 范围

- 以真实 `next_server` 和两个独立 `next_client` 进程运行至少 10,000 个 16 ms 固定 tick，实际窗口 175 秒，165 秒后开始三步停服。保留丢包、校正、重连、远端插值恢复和完整停服，不用空转或加速时钟替代。
- 记录服务器输入、客户端预测历史、未确认输入、插值样本、损伤队列、ENet 待发／待确认包和 Poll 事件高水位；销毁会话后仍保留生命周期峰值并核对配置上限。
- 正向三进程使用最小环境变量。发布目录只允许真实服务器、客户端、ENet 许可证和绑定构建产物的 `RuntimePackage.json`，禁止 Godot 可执行文件、项目格式和未声明文件；从发布目录再次完成同一闭环。
- CI 在 Windows、macOS 和 Ubuntu 上分别构建并执行真实 10,000 tick。平台结果不互相外推，干净源码树继续运行快速正负场景。
- `PredictionReconciler` 提供模型配置、有界历史、校正阈值、未确认输入快照和重置接口。Godot `GameplayClientPrediction` 只保留 Ref、限频、字典／数组和脚本错误语义适配，确认、重放、序号与校正不再维护第二份实现。
- 保留 legacy 的 `resynchronized`、重放计数、未确认集合和拒绝原因，实际重新编译 Godot 编辑器并运行 Gameplay 回归。

## 已验证

- macOS arm64／Clang 独立快速验收：21 个运行时测试、278 条检查通过；正向、负向、干净目录和发布目录真实闭环均通过。
- 真实长稳：10,312 tick、165.038 秒，服务器输入高水位 4、ENet 高水位 5；A 的预测历史与未确认输入高水位均为 6，B 的插值样本上限为 32。A 最终位置为 `3.072`，三步停服完成，两个客户端正常关闭。
- ASan／UBSan 下独立运行时与发布目录闭环通过；三份真实链接契约、23 个契约测试和 13 个构建工具测试通过。
- 87 文件无 Godot 源码树重建并完成发布闭环。最终输入集合的原生失效使 native key 从 `934d2bb3dfcc669694537e62292fabc5b1c12c91265e5c457812898eca02e58f` 变为 `1ff5bc3854f613d6883830bb6a4252fa57adc191055b3af781b0888f8b99a308`，默认 tick 从 1 变为 2；恢复后键和行为完全一致。
- Godot 编辑器与 `template_debug` 分别完成 29 个测试、4,846 条断言且零失败，覆盖共享 Reconciler、限频、重放、`resynchronized` 和真实 ENet 场景。

## CI 修复补充

- Ubuntu 动态依赖审核改用 `ldd`，macOS 保持 `otool`；新增真实脚本测试覆盖 Linux 分支，构建工具测试共 14 项通过。
- 客户端仅在收到有效服务器最终响应且已发送 `DrainComplete` 后，才把重复断开的 `NotFound` 视为已关闭；其他关闭错误仍失败。新长稳再次达到 10,312 tick。
- 最终平台修复的原生失效使 native key 从 `716585ca58d162793c5a0510573fd440b0bcbd472ead2e9e71d858ec4e4703a8` 变为 `280b2b45a74cefffc62506b640975555bfc2c7f3ed5e5ac3679c16a17dcf9c0c`，默认 tick 从 1 变为 2；恢复后键和行为完全一致。全部候选 Python 文件通过 `ruff format --check`。
- 追加证据：`data-collection/engine-next-headless-runtime-m2-pr5-ci-fix.json`。

## 第二轮 CI 修复补充

- Windows 不再把 Shell 语法的伪 `ldd` 当原生程序执行，而是显式通过 `sys.executable` 启动；同一个真实 Python 测试脚本可在 Windows 和 Unix 上覆盖 Linux 动态依赖审核分支。
- Linux 允许 `/lib64/ld-linux-x86-64.so.2` 等绝对动态加载器路径作为系统运行时，测试夹具包含该实际路径；`BuildGameplay` 与 `BuildRuntime` 使用同一规则，其他非预期依赖仍会被拒绝。
- 第二轮候选已运行 clang-format 22.1.5、Ruff 0.17.1 与 `ruff format --check`；14 个构建工具测试、21 个运行时测试及 278 条检查再次通过。
- 最新长稳为 10,312 tick、165.043 秒；服务器输入和 ENet 高水位分别为 4、6，客户端 A 的预测历史、未确认输入及 ENet 高水位分别为 6、6、7，两个客户端正常完成三步停服。
- 最终原生失效使 native key 从 `34591eb2421c68e789019be6e5f490134d2c57a8c26894c4129d6bbfd3885ce4` 变为 `d7659678e51be04a5e9f6bf8c84e94ecc48910e045d0e2ca59e849ae3c5c1a27`，默认 tick 从 1 变为 2；恢复后键和行为完全一致。
- 追加证据：`data-collection/engine-next-headless-runtime-m2-pr5-ci2.json`。

## 最终格式与 main 集成复验

- 已整合 main `69ed8de5c273395074fab49d9c48c1dc0baae00e`；主线新增内容不涉及 Engine Next 或 legacy Gameplay 原生输入。
- 全候选 clang-format 终检发现客户端关闭日志的一处换行问题，修正后重新执行快速、Sanitizer、干净源码树、发布包和长稳验收；第二轮旧原生键不再作为最终键。
- 最终长稳为 10,312 tick、165.034 秒，服务器输入和 ENet 高水位为 5、6，两个客户端正常关闭。21 个运行时测试、278 条检查及 14 个构建工具测试通过，M1 Trace 保持不变。
- 最终 native key 为 `428503ae6446583c3b7028fee0337c9a9998cc62f3a450939d70b7cb3ae2a4e5`；配置改为 2 tick 后变为 `1377f902d8eb8912450492da1a6038a6f528c0370c49d94ed3c908696d41fa8c`。失效二进制连续两次输出 2 tick，恢复后连续两次输出 1 tick且键完全恢复。首次构建后启动曾输出 1 tick，作为未复现的过渡异常记录，不据此宣称构建器缺陷。
- 追加证据：`data-collection/engine-next-headless-runtime-m2-pr5-ci3.json`。

## 签发基线复验

- 首次签发回读发现 main 前进至 `7acdf07ca4c89251527a392c754a536af2094b6a`，新增两个 Duobao 文档提交，与候选写入路径无重叠；阻塞事故为 `9c885a4b1e566963ccce77339644e3cc50eab4982a1c99bce3cfc15cd08ce4c6`。
- 已在合并提交 `92260105c38c5baef7030bec0790c2ee58ac4dfe` 整合该基线，原生输入未变化，无需重复引擎构建；原 module-impact 门禁已在同一工作树重新通过。
- 追加证据：`data-collection/engine-next-headless-runtime-m2-pr5-main-7acdf07c-integration.json`。

## PR #1214 平台失败修复

- Ubuntu 严格 C99 编译确认 `inet_aton` 未声明；Clang 的 ENet C 编译现在显式定义 `HAS_INET_PTON=1` 与 `HAS_INET_NTOP=1`，新增构建命令回归测试，构建工具测试共 15 项。
- macOS 长稳确认客户端在发出 `DrainAcknowledge` 后可能仅等待 32 ms 就提前断开。现在只有已发送 `DrainComplete`，或普通离开且不处于停服流程时，才允许调用 `DisconnectLater`。
- 新增仅用于服务器最终停服响应的 `--drain-response-delay-ms`，默认 0，真实正向闭环固定使用 96 ms。修复前二进制在同场景下两个客户端均失败、`acknowledged=0、forced=1`；修复后同场景两个客户端正常关闭、`acknowledged=2、forced=0`。全量服务器包延迟的尝试不纳入证据，因为它会改变重连场景。
- 最终快速、发布目录、干净目录、Sanitizer 和真实长稳再次通过；长稳为 10,312 tick、165.229 秒。M1 仍为 16 个测试、200161 条检查，Trace 不变。
- 最终 native key 为 `cde7ed9cdfa3e6fe0a9d4b7ef3809ca8411b02b9f8f1d7cdbd16f56d54d5a7b3`，失效后为 `0a8236dff2f312326e7d09b5ed4acc28f734372dd91d9033aa8e337f58bffd5e`；失效二进制连续两次输出 2 tick，恢复后连续两次输出 1 tick且键完全恢复。
- 追加证据：`data-collection/engine-next-headless-runtime-m2-pr5-ci6.json`。

## 重绑定基线复验

- PR 重绑定期间 main 前进至 `99a8e8cb1fb4e72dc135b9f655884984ab7909cc`，包含交付框架更新，但没有 Engine Next、legacy Gameplay、工作流或本候选证据路径重叠。
- 已在 `7869145e78da37e8dc8b7f50965ac4fdcb3aca07` 整合该基线，原生输入不变，原 module-impact 门禁再次通过。
- 追加证据：`data-collection/engine-next-headless-runtime-m2-pr5-main-99a8e8cb-integration.json`。

## 最终平台验收与收尾

- PR #1225 的签名 head `03144fe7de962658af218095e5067425630f7cc6` 已通过 Windows／MSVC、Ubuntu／Clang、macOS／Clang 真实三进程 10,000 tick、静态检查、Issue 关联和 Windows 编辑器检查。
- 该 PR 已合入为 `fe98b82a19da73c5339c9a21959f65950c62e73a`；main 运行 `43551606803` 的 Windows、Ubuntu 和 macOS 三个作业也全部成功。
- 总验收前 12 项已由本地、精确 PR 和 main 证据闭合，包括干净构建／运行、双客户端出生、权威模拟、预测校正、插值、重连、负例、优雅停服、有界长稳、链接发布边界、三平台和 legacy 回归。
- 最后一项是最终证据 PR 的合入与 main 回读；完成前 #1042 和 #1138 保持开放，不预写关单回执。
- 最终证据签发前，main 已 fast-forward 整合至 `8f3eaac66e67537fad415cf9db0edfdcba912714`；上游仅修改天璇桥接相关文件，与 Engine Next 原生输入和最终写入路径均无重叠。集成证据为 `data-collection/engine-next-headless-runtime-m2-final-main-8f3eaac6-integration.json`。
- 随后 main 又前进至 `5838241afad2c5f699f06a76b1c299c5560677d4`，新增 AI 工作流与天璇功能但未触及 Engine Next。树级自动集成报告冲突，真实 Git 检查则 fast-forward 成功且无内容冲突；恢复证据为 `data-collection/engine-next-headless-runtime-m2-final-main-5838241a-integration.json`。

最终平台证据：`data-collection/engine-next-headless-runtime-m2-final-platforms.json`。证据入口仍为 `engine_next/build-impact.json` 的 `evidence` 字段。
