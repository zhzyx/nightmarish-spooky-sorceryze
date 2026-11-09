# 按构建输入在并行工作树中安全复用 Godot 编辑器产物

实现宿主本机不可变产物、构建摘要和同键排他构建，独立工单验证和来源清单，安全回退、取消、损坏和工具链变化测试。集成编辑器自编译，不混用不同配置。与 CLI/CI 和业务包主责共享协议。

父工单 [#687](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/687)。独立交付 [#688](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/688)。目标为 main。

## 构建与验收

`tools/editor_native_cache.py` 通过当前目标实际执行的 SCons 平台配置，取得编译器、链接器、资源编译器、SDK 搜索目录、生成器 Value 输入及派生文件。共享入口生成的原生版本采用 Godot 源码归档的空 Git 哈希和零时间戳。命中时消费者独立记录本次 HEAD、生产者 HEAD、原生键、可执行文件与伴随产物的 SHA256。绑定工单的编辑器继续执行隔离启动、恢复用例和当前源码清单验证。

以当前仓库的 Git common directory 为基准，`gonggong-native-cache/` 保存各输入键的原生产物。各工作树以操作系统锁串行发布相同键。生产和命中均复读输入，生产者通过完整性检查后原子公布目录。消费者复制文件并复核摘要，损坏条目隔离后由当前工作者重建。天枢外置界面由消费工作树按本次请求重新打包。

本次共享覆盖实际可识别的 Windows MSVC 桌面编辑器，含 GUI 与控制台伴随程序。其他工具链、动态自定义配置及未登记的选项沿原有 SCons 路径构建。工作树的原生源文件、工具内容、SDK、配置及生成器输入按内容计入键。登记的运行时脚本、独立测试夹具和工单管理记录，由本次 SCons 原生依赖图核实归属后决定是否计入。

本机执行 `py tests/editor/test_editor_native_cache.py` 通过 8 项，覆盖两个工作树同键竞争、锁持有者退出、取消、损坏重建、失败与源码漂移、跨提交独立来源、工具和 SDK 变化。执行 `py tests/editor/test_editor_self_build.py` 通过 13 项，覆盖原始可执行文件与 macOS 应用布局及启动失败时的绑定。Windows 实际 SCons 探测识别 VS 18 的 MSVC 14.51、SDK 10.0.26100.0 及 GUI、控制台输出。完整原生编译和原生验收由父工单 #687 在整合候选上留证。
