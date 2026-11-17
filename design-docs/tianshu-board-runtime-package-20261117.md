# 天枢看板兼容脚本运行包

需求 ID：tianshu-board-runtime-package-20261117。父需求 #1382 的 P0-B 引擎业务包实施子项；上游 #1387 已完成源码消费者核查，由当前责任者独立校验 21 个源码摘要并接收契约。静态核查来源 a22d44c5，实施须核对当前 main 的实际消费者。

用户已于 2026-11-17 授权完整 AI 原生引擎与多 Agent 工作流实施，要求优化内嵌头、模块合入及独立迭代，同时保留至少 AA 写实沉浸渲染与 3D 能力。本项不改变渲染代码或 #951 控制器、#1343 渲染在途工作。

将 `daqian_board.gen.h` 的四文件兼容 Python ZIP 外置为版本化宿主包，桌面宿主采用 `tianshu-board-compat/1` 契约，原生侧只负责有界读取、摘要/ABI 校验和既有字段注入。保留 workspace.gd 的 legacy helper 摘要条件、现代宿主原脚本路径和 CLI/result 语义。包不成为完整业务权威，也不将可选 Git board 适配变成原生多宝的必需依赖。

实施范围：打包器、实际 SCons 输入与生成器、daqian_dock 原生装载、必要部署/安装清单与针对性验证。优先保持 `board_bundle_base64/board_bundle_sha256` 注入接口；如确需修改 workspace/controller 等在途文件，先确认具体责任并交接受影响范围，不接管他人副本。

固定拟议格式沿 #1387 审计：JSON envelope `{sha256,payload}`，payload 含 abi、version、bundle_base64、bundle_sha256 和严格四文件 entries 摘要。完整文件 pin 与 payload/ZIP 摘要分开。默认包路径、self_update 槽及 macOS Resources 参照已有 tianshu-graph/1；显式绝对路径与整包 pin 成对提供。不执行错误 ABI、错摘要、损坏/超限或越界 ZIP。宿主声明与现有可信包选择边界一致，不把内容摘要当授权。

验收：

1. 真实原生消费者从独立包读取；改变四个 Python 输入仅更新包，不重编/链接编辑器；改变原生加载器仍正确构建失效。Web/mobile 的嵌入回退按真实支持范围保留。
2. 同一 Windows 编辑器二进制上包 A→B→A，记录可观测行为、二进制及包摘要，拒绝错误 pin、未知 ABI、非法结构/摘要、超限与损坏包；不能用纯 Python 单元测试冒充原生装载验证。
3. 已启动会话固定包版本，新会话选择新版本；Windows 锁定替换失败保留旧有效内容，验证可回退。
4. 两个 legacy helper 摘要、现代 board_delta.py、未知/缺失 helper、缓存失败的既有执行/回退行为保持；新包失败有明确诊断，不假报已启用。
5. 既有图形包、启动检查与控制器接口的受影响回归通过；未支持平台或无法实测项明确保留。执行遵循 Godot 静默验证，先核对已有构建/安装/端口，不修改生产安装。

placement=mixed：原生装载器与独立运行包分别留证。输入是四文件源码、打包器与宿主 ABI；宿主接口是既有字段注入及 Python CLI。回退选择上一验收包并保留版本化缓存，不删除在途会话资源。临时构建/测试资产按实际终态清理，未交付源码和必要回退版本保留。

本项不关闭 #1382，不验收 AA 画质，不重新实现 Engine Next AICore/Executor/Asset/Scene，也不改变多宝原生存储候选。独立审查、正式门禁和 main 回读后方可作为已交付业务包报告。

## 已执行验证（2026-11-17）

最终候选基于 main `c472447b`。Windows MSVC 已真实编译新加载器，115 项 AIChat 原生测试通过。最终受测二进制 SHA256 为 `acfa5e808c8033e3aa0a31df4eb08fa9d5ba8a593f232c2786f6c120dbcd777a`。四个 Python 输入逐个修改仅更新包，编辑器摘要与修改时间不变；原生加载器变更实际触发编译/链接，试验后源码已恢复。

同一二进制完成安装包 A→B→A、会话固定、新会话选择、自更新槽、显式路径与 pin、错误 ABI/摘要/结构/大小/截断 ZIP 拒绝。另一真实入口试验通过原生 helper 参数和既有 Python bootstrap 执行离线 fixture，观察 CLI/result A→B→A；核验缺失 helper、缓存写入失败回退、子进程取消后无结果文件。原有两个 legacy helper、现代和未知 helper 分支保留。此行为 fixture 不代表线上 GitHub 工单或模型已验收；CLI terminate 也不冒充控制器取消，控制器的隔离取消由实际 multi_issue 原生回归另外覆盖。

图形工作台 graph 与 multi_issue 原生回归通过，Python 组件检查共 42 项通过（缓存新增故障例后为 14 项）；macOS 专属 15 项跳过。桌面外置与非桌面内嵌按消费者分别处理；未执行平台不外推。独立审查和补充取消传播探针通过，真实摘要、Git blob、命令、适用范围在 `data-collection/tianshu-board-runtime-package-1404.json` 及其引用回执中。

共享原生缓存曾在成功编译后因 Windows rename 拒绝访问导致封装失败；现仅将可选缓存保存失败降为 uncached，保留已校验本地产物，不重复编译、不吞取消或完整性失败。已完成定向回归和独立审查，原 OS 拒绝访问的底层触发原因未知。CI 增加独立 board 打包命令，覆盖缓存命中时的资源更新。

生产安装、workspace/controller 与四个业务 Python 源码保持原状；测试临时目录清理，构建/审查证据、隔离候选和必要缓存保留到交付核对完成。线上服务、其他平台和 AA 目标仍由父需求继续验收。本子项等待精确候选 CI 与 main 回读后关闭。
