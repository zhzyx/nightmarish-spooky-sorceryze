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

基线：`a18c04fc1`。当前 GitHub 操作者 `Sail-Li`，仓库权限 `WRITE` 已回读。GDScript PR #800 交付接口后，完整 Windows 套件发现语言关闭/重启后的临时缓存清理缺陷；PR #802 修复并通过完整 Windows CI，已合入 `7a99514ed14362a0bba047fa6da36209f3a2acc2`。C/C++ 已实现并独立审查通过，基于该 main 集成验证 debug/release 模板，等待原生候选 CI 与 main 验收。


## 原生接口与边界

`GDExtensionManager.compile_extension(compiler, arguments, output_directory, entry_symbol)` 返回 `error/exit_code/output/path/library_path`。它同步执行显式编译器参数列表，原子创建全新目录并拒绝已有目录，仅在动态库存在且描述文件写入成功后返回路径；调用方再显式 `load_extension`。描述文件绑定当前引擎最低版本，类冲突、实例释放、状态迁移及卸载由调用方管理。失败不覆盖运行中产物，失败目录保留供诊断。

当前实际验证为 macOS arm64 / Apple Clang 21 的 C 与 C++。GNU/Clang 风格的 Linux/BSD 与 Windows 分支已实现，但未声明这些平台已实测；MSVC 参数语法和移动/Web 原生编译不支持。外部工具链与 ABI 头文件是依赖，不捆绑编译器，不直接改写引擎自身类型布局。

来源：父 #795；GDScript #796 / PR #800；原生 #797（当前候选）。GDScript 夸父问题 #798 的原失败单元测试已在 PR #802 的完整 Windows CI 成功复验；本地原生初测缺失 compatibility_minimum 已复现并修复，测试断言失败曾使脚本不退出，运行器新增受限退出帧数避免该等待。

发布模板补充验证：release VM 会省略部分运行时错误检查，GDScript 初始化诊断只覆盖虚拟机实际报告的错误；API 文档明确该边界。两类模板均验证语法/类型诊断、有效静态初始化、依赖、脚本替换与缓存回收；初始化失败诊断在 debug 中验证。
