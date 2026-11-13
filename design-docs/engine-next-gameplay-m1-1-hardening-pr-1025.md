## 问题与目标

M1.1 实现 PR #1028 已合入并完成候选及 main 验收。本 PR 只补齐设计完成状态、最终交付证据和 `request_end`，不改变已验收实现，不启动 M2。

## 改动与候选

- 将 M1.1 验收清单更新为完成，并追加 PR #1028、候选 CI、main 回读、插值修复和双向 legacy 回退证据。
- 新增 `data-collection/engine-next-gameplay-m1-1-hardening-delivery-20261113.json`。
- 新增 R8 记录候选及 main 的实际远端检查，保留 R7 原始验证证据不改写。
- 新增 `request-end-1025-engine-next-m1-1-hardening` 事件及同需求来源索引。
- 目标基线：`1ba44e0271e44bf30a43188b2d1a1df4574fa7bf`；目标分支：`main`。

## 验证与数据

- 独立 Release：16 个用例、200161 条检查通过，构建目录与干净目录一致；ASan/UBSan 同样通过。
- 真实链接契约：14 个源文件、19 个本地包含、7 个对象、1 个静态库，`sources_passed`、`link_passed`、`contract_passed`。
- 完整 Gameplay：29 个用例、4846 条断言通过；四个 API 结构保持一致。
- 正常 Trace 摘要保持 `f55d1f5bc85bb72376d3f31cdf9b64aac91e714b6556dbce1663c1db7995924c`。
- legacy 回退排除了全部 `engine_next` 和适配器消费者；恢复 M1.1 后重新包含两个内核实现和适配器，恢复编辑器 SHA-256 与回退前一致。
- PR #1028 候选及 main 的 Windows MSVC、macOS Clang、静态检查和 Windows 编辑器检查全部成功。
- 本地复核再次通过独立构建、链接契约、ASan/UBSan 和完整 Gameplay；没有未验证的 M2 声明。

## 未验证项与交付状态

- 不包含完整 `next_runtime`、动态库热更、渲染器、脚本、编辑器或 M2。
- 本回执 PR 合入后关闭 #1025 和已恢复的环境排障单 #1026，并回读终态；在发生前不预填完成。
- 当前执行责任：Kimi Work 会话与已验证协作者 `kaiyunxue`。无模型用量或外部服务用量声明。
