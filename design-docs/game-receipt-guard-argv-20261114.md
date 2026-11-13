# 游戏回执保护参数在原生宿主中完整传递

<!-- gonggong-request:game-receipt-guard-argv-20261114 -->

关联 #1075 的兼容回归、父 #830、总目标 #978。当前用户已授权 AI/GitHub 接入排障修复，并明确移交 #830 交付；本单不接管 #951/#773 原生产或安装。来源 main 4eacf 的 GameReceiptGuard.cpp 在macOS调用OS::execute并捕获stdout。实际Unix实现通过popen组装双引号字符串，未转义嵌套JSON，引号被shell去除，原生状态引导在明确开始后停在provenance_guard_failed。保留的私有诊断明确JSONDecodeError发生于json.loads(args.game_reporting)，原60f2/新6069都使用同一模块。本单不修改通用Unix OS行为。

范围：复用现有原生进程能力，让受验证工作区、Python/helper路径与reporting内容以真实参数传递，消除shell重解释，保留安静执行、错误退出及有界失败诊断；不删掉回执保护，不将fixture当生产准入。不扩展权限，不改变回执/guard算法。实际参数含空格、引号与shell元字符时保持原值且不能产生额外执行。必要测试修复仅限原生guide隔离安装缺失依赖、合法的外部私有回执目录和macOS私有cache，旧测试断言不得放宽。

验收：原状态引导复验达到一次明确Start、一次原文模型请求、真实本地回执，direct状态拒绝与重试仍零写零模型；参数边界定向验证、原生构建、独立审查、适用精确CI/main回读。#1075历史保存原验收另行保持，未交付不关闭相关单。
