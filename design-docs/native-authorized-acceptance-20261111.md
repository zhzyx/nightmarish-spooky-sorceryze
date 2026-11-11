# 原生独立验收与同事件依赖接续

工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/783

父需求：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/776

需求 ID：`native-authorized-acceptance-20261111`。本实现遵循父设计 `authorized-production-acceptance-20261111.md`，消费 #776 的可信验收桥接、#785 的真实外部执行登记和 #792 的显式修复谱系。本文路径以仓库根解析。

## 原生责任与接口

`AIChatDock` 保存独立的 `acceptance_reviews`，原生产批次持续存在。工单必须显式逐行声明 `- 验收: ID | 可验证要求`；缺项、重复项和含混项不从自由文本推导。正常设计提示要求输出这些声明。

生产完成仅作为启动独立只读审查的条件。原生宿主登记实际生产者与审查者身份、原批次 token、工单、定稿摘要、终态回执、精确候选和全部验收项；模型只能提交判定和证据路径。成功的实际文件读取由宿主记录其字节摘要。完整 verdict 必须覆盖全部唯一验收项，证据必须实际读取且仍匹配候选。

审查者可读取宿主已登记的生产终态和外部执行登记回执作为上下文。此类读取必须同时匹配登记绝对路径、实际读取摘要及当前原字节摘要，结束时再次核验；摘要不符不能重新登记为其他上下文。自动验收审查中，其他已获工具授权的成功外部读取（如上游源码或真实执行日志）只记录为不受信辅助上下文，固定读时原字节摘要、拒绝重复读取时重新绑定，并在完成时复核。两类上下文均不进入候选证据映射，不能作为验收项证据；普通委托审查的来源规则保持不变。目录、脚本列表和日志读取由实际宿主回调明确报告成功或失败，缺少明确结果仍保留未知。此边界修复真实 Codex 多工具审查中发现的 #794；既有 build18 夹具未覆盖该组合，不作为该修复证据。

外部工作者使用 runner 生成的 `execution_id`，不伪造模型 conversation。启动前保存配置路径、原字节摘要及 order/worktree/workerId；完成后核对真实 registration、terminal 原字节、PID、退出状态、登记来源、定稿和修复谱系。只读审查沿现有候选 checkout 验证器授权，不放宽根、分支、公共 Git 目录与 base 约束。

原生通过可信安装中的 `tools/gonggong_bridge.py` 异步调用 `acceptance-capture`、`acceptance-verify`、`acceptance-current`；候选工作副本不能替换验收实现。主线程只轮询已启动进程，不同步扫描全仓。`acceptance-current` 消费验证器返回的同次快照，覆盖新增、删除、字节、根与 Git 身份。成功验收须把决策和历史持久化并回读一致，才允许依赖消费。缺少 Node 台账映射只允许桥接明确返回的 editor-only 情形，不宣称台账已放行。

所有后台任务绑定原批次、当前来源和一次 nonce，超时为 600 秒。验证前写入宿主私有存活文件；停止、关闭和超时先撤销同批次存活标记，再终止进程。桥接及真实派发在自身关键边界再次核对存活状态。旧历史不恢复活动批次，不自动重放旧 token。

## 失败修复与依赖消费

完整、来源仍有效的 `fail` 只能触发一次当前生产者修复。宿主保留失败原文与原始回执，重置旧 capture/verify/current 与审查上下文，修复完成重新独立审查。串行沿原生产候选继续；外部生成原字节失败决策及 `repairOf`，由 #792 的独立修复票据产生新 execution，保留旧票据与回执。`unknown`、来源漂移、权限缺失与取消均不视为可自动修复的失败。

具体审查发现由原父批次携带并一次回传；无法继续的已完成审查通知原父会话，下游保持阻断。取消明确停止，不自动重新开始。

并行下游消费当前仍匹配的已验收前驱；提示附 `HOST_ACCEPTED_UPSTREAM`，包括实际根、决策摘要/路径、终态引用、验收项和证据路径。只授予读取这些绑定上游的范围，写入仍限本工单工作副本。原生调用原 runner，保留已完成子项并依靠实际票据避免重复启动。

## 构建边界与验证

归属为既有编辑器原生边界：`ai_chat_dock.{h,cpp}`、`ai_chat_sub_agents.{h,cpp}` 参与编译；`tests/editor/test_native_acceptance.cpp` 通过测试链接登记。改动使构建键失效并生成新二进制；回退使用已验证旧二进制，不改正在运行的安装。桥接和 runner 是独立宿主工具，分别由 #776/#785/#792 管理输入、门禁和发布，本单只消费其固定接口。

`tests/editor/run_native_acceptance.py` 使用真实原生完成回调、实际文件读取、真实 Python/Node 验收和台账；HTTP 模型与 GitHub 传输为隔离夹具。并行场景使用真实 runner、独立 Git worktree、实际子进程和 Windows 已安装 Job Object 扩展。扩展通过 `NATIVE_ACCEPTANCE_JOB_OBJECT` 指定可信绝对路径，未提供时从本检出安装位置寻找，缺失明确报错。`native_acceptance_parallel.py` 提供三工作者和真实台账准备，C 实际读取宿主附带的已验收上游。

精确输入、构建、成功/阻断矩阵及已知限制记录在 `data-collection/native-independent-acceptance-783-final.json`。`native-independent-acceptance-783.json` 保留 build18 的已上报原始证据，后续格式归一后的最终候选另存，不覆盖既有引用。原始私有夹具日志保留在忽略的 `bin/`，公开证据不复制凭据、模型原文或临时工作区内容。夹具验收不替代 #773 的真实模型游戏业务验收；该组合由父任务沿同一原生入口继续核验。
