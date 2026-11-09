# 将编辑器二进制复用接入命令行构建和 CI

使实际 Windows 构建入口可参与同一构建去重，在 CI 中安全复用并保留每个候选的验证证据，避免候选分支 push 与 PR 的重复全矩阵。不可信来源和不同编译器/SDK 不共享可信产物。保留精确签发和必要检查，独立配置仍可同时编译。

父工单 [#687](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/687)。独立交付 [#690](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/690)。目标为 main。
