# 多宝原生宿主输入的精确构建边界

需求 ID：native-host-inputs-20261117。父 #1382，用户授权的 AI 全链路效率优化；保留现有 AA 渲染与构建真实性。

已在可信 main 交付的天璇/多宝原生存储、证据、发布、工作快照与认证 API 是独立 Python 宿主工具。tools/native_host_inputs.json 尚未列出这些具体文件，导致后续修改仍可能失效完整编辑器产物。按实际消费者补齐已验收文件，减少无关编译等待。

范围只含 main 75eef9a901e782d69546b3eef00382bdc4eabf47 已有的原生多宝及其服务接入文件。使用明确文件清单，不使用目录通配、扩展名豁免或预登记未来模块。新增原生/嵌入消费者仍覆盖宿主清单；tools/ainative/owned_process.py 等实际嵌入资源不进入独立宿主清单。本次不修改缓存或 CI 决策算法，不追改他人的候选。

验收：

1. 每个新增条目存在于可信 main，说明运行入口与独立宿主归属，实际 SCons 原生依赖图与新增/完整宿主清单均无交集。
2. 已有宿主身份测试证明独立工具变化不改原生产物身份；真实生成器消费同一文件后必须失效，未知输入及损坏清单保持保守路径。
3. 仅修改精确清单、必要说明及证据；本候选仍按基线策略执行全部适用门禁与 CI，不以新增清单自行豁免。
4. 独立审查、main 回读及真实工单结束后，后续变更才可消费该清单。

placement=host_tool 元数据维护，输入是已验证源码和实际 SCons 图；不新增模块或引擎运行时。回退为恢复前一清单，保留完整构建保守行为。记录实际执行平台与耗时，不估算 token 或未经测量的提速比例。

## #1434 本地验证与交付边界

2026-11-17 在可信 main `75eef9a901e782d69546b3eef00382bdc4eabf47` 的隔离工作树核对 17 个已交付文件：多宝 NativeStore/CLI/进程验证（4）、EvidenceCache 与文档/测试（3）、NativeRelease 与文档/测试（3）、NativeWorkspace/CLI 与文档/测试（4），以及服务 native_api.py、test_native_api.py、test_native_platform.py（3）。既有 README 与 API 主入口已在清单内，不重复添加。逐项路径、可信 main blob、SHA256 和运行入口绑定见 `data-collection/native-host-inputs-1434.json`。

实际 SCons 4.11.1 在 Windows 11、Python 3.14.3、MSVC 14.51.36231 环境，以 platform=windows、target=editor、dev_mode=yes、debug_symbols=no、accesskit=no、angle=no、d3d12=no 探测 9,378 个原生输入；新增 17 项以及完整 134 项清单均零交集。探测为 dry run，不编译引擎。配置仅支持此次平台与选项的实测结论；其他平台继续使用原消费者覆盖与保守回退算法。

候选清单上的 `tests/editor/test_native_host_inputs.py -v` 3 项及 `tests/editor/test_editor_native_cache.py -v` 14 项全部通过，无跳过。真实 SCons 仓库图和生成器消费测试与合成 Git/cache 身份测试分别记录，不将 fixture 身份复用解释为完整编辑器构建提速。未知相邻文件、新消费者、清单修改和损坏清单均保持原失效或不发布缓存行为。

本子任务只完成本地清单和证据，独立审查、正式门禁、CI、main 合入及 Issue 结束由父会话继续。清单生效前不以本候选自行豁免其构建或 CI。
