# 马良稳定性：动态复核、生成结果与服务配置持久化

<!-- gonggong-request:maliang-stability-batch-20261120 -->

## 工单与范围

- Issue：#1625；关联配置工单 #1624。
- 基线：`origin/main`，最终候选基线由正式提交门禁回读。
- 本批共享工作台与原生验收文件，作为同一候选交付。

## 实现契约

1. 输入分析生成动态 `review_plan`，基础五视角检查三维产物，细节区域由用户命令和真实参考图决定。渲染回执绑定计划与模型 SHA，Review 报告逐项校验，缺项只补审缺失视图；旧记录保留兼容恢复。
2. 工作流保存时嵌入完整生成结果及原始字节，重开后从内容寻址文件直接预览，不恢复执行权限，也不重新调用生成服务。覆盖单图、图像集和 GLB。
3. 按 #1624 移除 offline 服务模式，分服务持久化草稿和工具路径；显式保存才激活运行配置，本地复制不依赖生成服务。

## 验收

- AINative Python 全量测试通过。
- 手部、盔甲、非人物动态 Review 及真实 Godot 渲染通过，实际安装 bundle 哈希一致。
- 工作流保存／重开、配置切换／重开、未激活草稿和旧配置迁移回归通过。
- 当前编辑器构建及隔离原生验收通过，正式门禁、精确候选 CI 和远端 main 回读完成。

验证结果写入 `data-collection/maliang-stability-batch-20261120-validation.json` 与 `data-collection/generation-service-profile-persistence-20261120-validation.json`。合成夹具不构成真实模型推理证据。

## 工作流持久化验收返修（2026-11-20）

4. 输入路径与对应快照同时保存；旧工作流的空路径从快照恢复到 `assets/inputs/`，图像集成员缺少 `description` 的历史文件保持可读。
5. 使用系统文件选择器和可见路径入口打开工作流，成功保存／打开后记住最近文件，重启优先恢复该文件而不是创建空图。
6. 本次执行节点的非空输入路径资源不存在时，阻止执行、清空路径并弹窗；不相关分支不受影响，不以快照静默替代缺失路径。

返修验证写入 `data-collection/maliang-stability-batch-20261120-workflow-followup-validation.json`。真实界面使用用户保存的 `TESTSAVE.json` 只读验证，文件 SHA-256 保持不变。
