# 引擎运行时编译

用户目标：基于现有引擎支持运行时编译代码。2026-11-11 当前 Codex 会话确认：GDScript 与 C/C++ 都需要，先实现 GDScript。本会话负责实现、验证及既有 PR 交付流程。路径均以本工作树根为基准。

## 范围与拆分

1. `runtime-gdscript-20261111`：在现有 GDScript 模块增加面向运行时的源码编译接口，返回脚本或结构化编译诊断；成功后可实例化执行和替换对象脚本，失败不改动现有运行脚本。覆盖成功、语法/类型错误、重复编译、相对依赖及隔离 headless 运行。
2. `runtime-native-20261111`：基于现有 GDExtension ABI 增加本机 C/C++ 编译及加载入口，显式指定外部编译器，使用参数数组调用，不通过 shell 拼接；保留编译输出、返回码及加载结果。覆盖 C 与 C++ 编译、调用注册的方法、编译失败、缺失编译器、重新编译后使用新产物。目标先为当前 macOS arm64/Apple Clang；其他桌面平台支持边界明确记录，移动/Web 无法执行本地编译器时明确拒绝。

父项 [#795](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/795)（`runtime-compilation-20261111`）负责完整验收及示例文档。GDScript 子项 [#796](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/796)，原生子项 [#797](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/797)；原生父子关系已回读。两个子项不共享实现写入，GDScript 先完成；原生项复用引擎已有加载器，不引入自定义机器码调用 ABI。依赖外部编译器和匹配的 GDExtension 头文件，不承诺运行时修改引擎自身 C++ 类型布局。替换脚本的状态迁移由调用方显式控制，不暗示任意存量实例可以无损热更。

## 构建与验收

新增 C++ 接口属于原生构建输入；文档与运行样例为独立资源。复用现有模块及构建依赖，不增加框架 Agent/Skill 定义。先编译受影响模块，再链接隔离候选，并以同一候选执行 headless 测试；不替换用户当前编辑器。使用当前源码的 module build placement 经验，输入变动后检查 SCons 失效；回退通过恢复上一个已验证引擎和保留旧编译产物完成。

结束条件：两个子项对应真实行为通过验证、独立审查、正式门禁、精确候选 CI、main 回读及各自工单验收关闭；部分完成不关闭父项。不修改其他工作树或现有未跟踪事件。

## 当前来源与状态

基线：`a18c04fc1`。当前 GitHub 操作者 `Sail-Li`，仓库权限 `WRITE` 已回读。CLI 位于用户本机工具目录；沙箱内网络失败，通过已授权网络执行通道回读成功。GDScript 接口与首次运行测试已通过；正在独立审查，C/C++ 尚未实现。
