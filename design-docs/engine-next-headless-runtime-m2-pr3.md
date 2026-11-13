# M2 PR3：权威移动、预测校正与远端插值

## 范围

- 新增固定格式 `input`／`snapshot` 协议，服务器按实际 PeerId、SessionId、EntityId 校验所有权和固定步长。
- 每实体每 tick 最多消费一个有界输入，使用 M1 PredictionModel 权威模拟；快照以“实体 × 接收者”广播，不再只发送给属主。
- 新增共享纯 C++ PredictionReconciler，客户端立即预测，确认后回到权威状态并只重放未确认输入。
- B 以服务器时间线和 M1 InterpolationBuffer 观察 A 的移动；快照使用可靠有序通道，输入使用独立数据通道。
- 调试 Trace 保留协议类型、实体归属和远端样本，便于区分传输、归属和插值问题。

## 实际验证

- macOS arm64／Clang：10 个运行时测试、141 条检查通过。
- A 连续 24 个移动输入后，确认序号为 24、未确认历史为 0、位置精确为 `3.072`、校正次数为 0。
- B 对 A 的远端样本进入 `interpolated`／`held`，位置大于 0，样本数至少为 2；构建目录与干净运行目录结果一致。
- 81 文件无 Godot 源码树重新构建并完成同一闭环。
- 三份源码＋真实链接契约通过；服务器／客户端各 23 个对象和 1 个静态库，测试 29 个对象和 1 个静态库。
- ASan／UBSan 下同一闭环通过；M1 为 16 个用例、200161 条检查通过，Trace 保持 `f55d1f5bc85bb72376d3f31cdf9b64aac91e714b6556dbce1663c1db7995924c`。
- 原生失效：native key 从 `3fac2c4becd823ab30631848ed6a4df2e9b49c267b79c373645b15cbfa553d41` 变为 `393136dac100bde0b6b7a970757c11b823b36ffe1024c5bb67b4d45db5821aad`，默认启动从 1 tick 变为 2 tick；恢复后键和行为恢复。
- clang-format 22.1.5、Ruff 0.17.1 和第一方 codespell 检查通过。

证据：`data-collection/engine-next-headless-runtime-m2-pr3-verification.json` 和 `data-collection/engine-next-headless-runtime-m2-pr3-build-impact.json`。

## 未验证与后续

- Windows MSVC 和 Linux x86_64 仍需精确候选 CI 实测。
- 本切片不包含网络损伤下的强制校正、重连、stale_held、优雅停服或 10,000 tick 长稳；#1042 保持开放并继续第四片。
