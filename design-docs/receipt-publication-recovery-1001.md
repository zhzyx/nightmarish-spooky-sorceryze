# 原生回执发布与诊断恢复

<!-- gonggong-request:kuafu-run-43286058093-attempt-1 -->

来源：[Issue #1001](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1001)，原工单 #994。授权 `codex-user-ai-github-integration-refactor-20261112`；修复责任者 Sail-Li 委托的当前隔离工作者。所有持久路径以 repository_root 解析。

原 main `308bc83c19ae7cd1811496cca0e7062e6b30dab0` 的 Windows CI `43286058093` 在 requirements-intake 第二次开发前失败。其初始原因仍未证实；后续 main `c6b7baa72f63c36a2fcd4063c8ed84300ee343fe` 的 CI `43296439174` 已通过，这不是原候选根因或恢复的证明。已复现的缺陷是在已完成持久动作之后，最终回执的单次 replace 失败会逃逸；原生宿主随后无法区分缺失、读取失败和解析失败，并删除无效回执。

## 实现与边界

- bridge.py 完成动作后写入同目录临时回执；仅 Windows sharing/lock 错误 32/33 重试原子替换，最多六次、截止预算一秒。永久访问拒绝不重试；失败退出 2，输出固定字段诊断并保留临时文件。绝不重跑原动作，也不新增远端副作用。
- 原生读取先取得子进程退出码。Windows FileAccess 将明确的共享/锁冲突映射为 ERR_BUSY；普通拒绝保持永久错误。原生最多六次、一秒内重读；等待期间维持 PID、队列及代际绑定。缺失、读取失败、UTF8/JSON/类型无效分别失败关闭；仅实际消费的有效结果移除原回执。
- 无效原始回执保留在私有缓存；公开诊断只有状态、退出码、错误编号、尝试次数、解析行和临时文件存在状态，不含解析消息、stderr 原文、路径或用户内容。成功消费后清理其诊断文件；失败文件交由原责任链取证。
- requirements fixture 在清理目录之前（含超时/启动异常）保存 `.receipts.json`；每组最多 64 文件，每文件最多读取 1 MiB，保存状态、大小、SHA256 和身份哈希。记录 final/tmp/outbox 的存在与解析状态，既有产物通配上传覆盖新增回执。
- 修正 UI 对“队列已保留”的不实断言；动作可能已完成且 outbox 已清空，界面只声称后续执行受阻。

## 验收与验证

Python 测试复现单次暂态、持续锁、永久拒绝、写入失败；核对真实 flush 的存储动作仅一次，临时结果字节保留；诊断测试覆盖清理后摘要存活、秘密不导出、读取失败及大小/数量限制。原生测试覆盖损坏 JSON、错误类型、缺失回执、重读预算，以及 Windows 真正独占句柄释放后读取原字节。

新增 header 属既有 native AI Chat 实现，修改后需重编译消费对象；Windows 文件实现同属原生输入。诊断 Python 是既有测试宿主辅助工具，不创建新模块、插件或运行时契约。回退需要恢复同一候选中的原生与桥接源码及对应已验证二进制，保留失败私有证据。父责任者负责原生构建/Windows 精确候选 CI、独立核查、正式门禁与 main 交付。当前工作者的 Python 通过不代表这些步骤已完成，也不代表原工单业务整体验收。

已召回 editor-dependency-handoff 的 bind-consumer-release 与 await-terminal-observers：按实际源字节、终态回执和消费者验收放行；单个成功进程或运输通知不能替代下游验收。本次保持原失败未知，不推断原故障由 Windows 锁造成。

公开验证：[data-collection/receipt-publication-recovery-1001.json](../data-collection/receipt-publication-recovery-1001.json)。任务临时 Python fixture 已由上下文管理器删除，无 GUI、应用替换或生产服务调用；未提交工作树保留供父责任者整合与验证。
