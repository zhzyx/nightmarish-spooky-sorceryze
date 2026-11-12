<!-- gonggong-request:parallel-runner-linked-entry-20261113 -->

# 并行执行器链接入口

父需求 #978，缺陷 #1005，关联目录恢复 #992。路径相对仓库根。

实际 macOS 原生并行验收通过安装 tools 符号链接启动 tools/godot_parallel/runner.mjs；旧入口用 argv 绝对路径比对 Node 已解析链接的模块地址，条件为假，退出0且没有结果回执。两个上游工作者显示 interrupted，下游无法启动。

入口改为比较两个路径的真实文件身份。普通绝对路径、含空格安装链接和 preserve-symlinks-main 均进入同一真实输入验证；作为模块导入保持不执行。能力选模、工单、候选、依赖、进程隔离和实际结果判定保持原实现。

新增 entry.test.mjs 在旧源码真实失败（0!=1），修复后与 preflight 两项通过。实际 native parallel 重跑及精确 CI/main 另附事实；未知与失败不得冒充验收。和 #992 使用同一隔离候选，仅因该启动缺陷阻止其真实消费验证；两张 Issue 按各自验收回读。
