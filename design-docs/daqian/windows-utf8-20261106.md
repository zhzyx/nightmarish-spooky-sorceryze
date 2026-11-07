# 天枢 Windows 调试结果编码修复

稳定需求 ID：daqian-windows-utf8-20261106。路径以仓库根目录为基准。用户要求编译、排查并提交天枢编辑器问题，确保当前 main 的编辑器源码包含天枢。

工单：[Issue #156](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/156)。

当前 Windows 源码构建的编辑器通过图和入口原生检查，但并发图中两个 Python 模型工作者的结果含损坏的中文及图片尺寸，导致汇合验收失败。Python 管道默认 GBK，Node 调试宿主按 UTF-8 读取。修复限于 `customizations/components/godot-host/daqian/debug_session.mjs` 的调试工作者进程环境，并保留已有进程环境。目标平台为 Windows；验收为本机构建成功、天枢图、入口、并发、输入与多工单原生检查通过，启动 `samples/gonggong-workbench` 的天枢编辑器窗口。停止条件为上述本地验证和仓库交付门禁完成。真实供应商调用及 macOS 运行不在本次复测范围。

本地核验：更新至主线 `17627640` 后，Windows 编辑器重新编译成功；图、入口、并发、输入、多工单原生场景均通过，五项使用同一编辑器 SHA256 `2cb78e7117b5e56efd2d17905c19ca08ecc2394f0a6e5f40b99775494c1fe07c`。先前的主线构建已启动 `GongGong Workbench` 窗口且响应；更新后的编辑器在提交前重新启动核对。`bin/` 为本地构建产物，不纳入 Git；main 交付对象为一套包含天枢的编辑器源码。
