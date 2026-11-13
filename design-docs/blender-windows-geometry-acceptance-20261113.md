# Windows Blender 几何验收

<!-- gonggong-request:blender-windows-geometry-acceptance-20261113 -->

父需求 [#978](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/978) 要求复核所有 AI 接入及原验收。关联 #840/#842 的三项实际 Blender 几何测试此前未执行；PR #1053 已补齐 macOS 等价离线 CLI 夹具，原 Windows C# 路由仍未覆盖。本子项由当前 Codex 会话在父需求授权下独立交付验证入口及实际 Windows 证据，不接管原 #840 发布或人物/供应商质量验收。

目标 Windows x64，基线 main `da9bfac7b5036f24d9657179d394dc2db3a66526`。新增独立 CI 工作流及小型测试运行器，调用 `tools/ainative/test_sculpt_provider.py` 中原三项测试，保持原 C# 夹具、测试方法与断言。运行器拒绝缺失 Blender、错误平台、缺失编译器、测试失败和跳过，不用零项执行冒充通过。保留源修订、源码与运行时摘要、原生回执、GLB 摘要和失败日志。

CI 只使用校验和固定的官方 Blender 4.5.11 LTS Windows x64 ZIP，解压到 runner 临时目录；无需模型凭据、不调用真实供应商、不下载模型/人物资源。使用隔离的用户目录和配置，在执行阶段阻断 Python 与 Blender 程序的出站访问；原 C# CLI 为固定离线夹具。下载、执行及证据上传分开；任务结束清理临时 runtime、配置及进程，必要审计产物作为 artifact 保留。不是用户安装器，不改全局个人配置。

验收：

1. 在真实 Windows runner 执行 `test_synthetic_cli_real_rounded_loft_cups_reaches_strict_receipt_gate`、`test_synthetic_cli_real_blender_organic_mesh_receipt_and_recovery`、`test_synthetic_cli_real_character_retains_original_and_expanded_receipts`，三项执行、零跳过，原严格回执和恢复断言通过。
2. 缺失运行时/编译器或平台不符时明确失败，任何测试错误不能被 artifact 上传或清理步骤覆盖。运行/计划/输出与实际候选绑定；不把受控离线计划当真实模型质量。
3. 工作流由本入口、相关几何源码或测试变更触发，并保留手动入口，无定时扫描；只读仓库权限，无生产服务秘密或用户安装副作用。
4. 通过必要局部检查、独立审查、正式门禁、精确候选 CI、main 回读和同一 Windows 作业验收；失败进入当次排障。记录实际清理，原父单及未满足整体条件的关联单不提前关闭。

写入范围为新的 `.github/workflows/blender_geometry_windows.yml`、`tests/editor/run_blender_geometry.py` 及针对运行器的必要失败路径验证、本文和本子项采集事件。无需产品实现修改；若实际测试发现产品缺陷，先保留精确复现并按父需求范围修复、复验。既有通用 CI 门禁不放宽，原 #830/#825/#948/#951 等任务责任及有效安装仍保留。

路径以仓库根为基准。官方运行时来源为 https://download.blender.org/release/Blender4.5/ ，ZIP 的 SHA256 为 `e11d3a8e4d4249be5a7db4a9325c1f670037d4233467c3b0bda181001efe44d3`，取自同目录 `blender-4.5.11.sha256` 并与此前已验证官方清单交叉核对。原始外部清单、下载及故障证据仅存宿主私有 receipts；生产代码与历史采集记录不覆写。


## 2026-11-13 原 Windows 路径验收

PR [#1061](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/1061) 已合入 main `481f0e820437f5e5d9218ee11ee2fe551109d86d`。签发候选 `1bf798e153e52397e8f4fbe4d6884cd0c066fd69` 的几何作业 [43425883079](https://github.com/zhzyx/nightmarish-spooky-sorceryze/actions/runs/43425883079) 和主线作业 [43428105337](https://github.com/zhzyx/nightmarish-spooky-sorceryze/actions/runs/43428105337) 均实际执行原三项 C# 夹具测试，3 run、0 skip/error/failure。两轮各核验90份源码与75份产物、原生回执和GLB；正常TLS取得的完整归档分别匹配GitHub服务器SHA256，用户配置/进程、便携运行时及两条临时防火墙规则均清理成功。适用通用Windows CI同时通过；范围跳过不计执行。

公开摘要见 `data-collection/blender-windows-geometry-accepted-1059.json`；原始归档及摘要按其中明确基准解析。该结果补齐#840此前缺失的Windows三项几何验证，不代表真实供应商质量、所有人物场景或有效用户安装，原#840及父#978整体范围继续保留。收尾对最终证据独立核验与正式补交，关联工单须在最后回读后办理关闭。
