# macOS 启动验证与资源包复验

子编辑器使用父编辑器实际加载的 UI 和看板资源路径及 SHA-256。日志中的 `TIANSHU_UI_LOADED` 和 `TIANSHU_BOARD_LOADED` 分别记录子编辑器从原生加载器取得的摘要，可与冻结清单逐项比对。两包及 AI Chat 入口均通过后输出 `GongGong macOS startup validation passed`。缓存按两包内容取键，复用时输出 `GongGong macOS startup validation reused`。缺包、摘要不符或看板退回兼容路径时会报告失败，下次启动重新检查。

在 macOS 上，从仓库根用 `python3 tests/editor/run_macos_startup_validation.py --app /path/to/Candidate.app --manifest /path/to/common.json --report /path/to/report.json` 复验。输入为已签名候选和该候选冻结的 `desktop_packages` 清单。脚本在私有应用副本上用 Cocoa 驱动启动隔离项目，检查首次自动验证、缓存复用、两个包各自缺失、损坏、变更及恢复。无窗口、脚本、命令行工具与恢复模式启动跳过自动探针。像素、原生窗口焦点和实际显示缩放仍需按对应工单验收。
