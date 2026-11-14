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
- Windows、Ubuntu 和 macOS 的精确候选 CI、main 回读及完整 M2 清单核对完成后，才能关闭 #1042。

证据入口：`engine_next/build-impact.json` 的 `evidence` 字段；最终验证记录位于 `data-collection/`，未生成的项目不预写通过。
