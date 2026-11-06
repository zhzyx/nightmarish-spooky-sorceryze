# 修复 Windows 可复用工作流的调用权限

[Issue #207](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/207) 对应稳定请求 gha-windows-caller-read-permission。用户要求修复全部阻塞。司南协调的实际 Codex 工作子代理 /root/authority 接收夸父 0.5.0 的阻塞处置职责，使用 GitHub 写协作者 Sail-Li 身份交付该项。

main 的 push 运行 42250157931 和 PR 的 pull_request 运行 42251651308 均在创建作业前失败。工单记录的 GitHub 注解指向 consultation-native 和 daqian-native-reuse。二者读取 Actions 运行及产物，需要 actions: read，同时检出仓库需要 contents: read。修复限于 .github/workflows/runner.yml 的 windows-build 调用；验证真实 push/PR 的工作流创建、静态作业及按原条件的 Windows 分支，完成后向依赖项回填运行、候选和 main 回执。若受仓库变量或其他独立服务故障影响，单独登记真实状态。
