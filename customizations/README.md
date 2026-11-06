# 共工接入与定制

[按平台查找共工接入子模块](platforms/README.md)


核心与接入的细粒度职责、当前实现映射及新平台／工具按需扩展流程见 [接入子模块边界](module-boundaries.md)。该文档定义职责结构；逻辑子模块不等于已拆分的代码或已启用能力，现有 platforms/components.json 与有效发布继续表示实际状态。

当前只有共工一个框架。framework/ 保存核心 Agent、治理、协调、采集及现有配套实现；目录存在不代表业务能力属于核心。Git 与 Godot 接入由本目录 components/ 管理，平台实现按 platforms/ 分类，当前宿主组件归属与证据见 platforms/components.json。

文件采集适配位于 customizations/platforms/data-collection/git-files/storage/，直接复用谛听规范，按离线分发注册表的 platform_files 单独核验；不再存在双框架同步豁免。新事件写入 gonggong-diting-data/，旧 olympus-hermes-data/ 仅按原身份读取。所有模块必须具备真实采集绑定和代表任务回执，配置不等于接通。

任务专有流程留在接入层；通用化提案可使用 tools/customization_feedback.py，经过共工治理与准入后再纳入核心。提案、导出或本地验证不自动产生批准。现有工具只准备候选材料，不自动替换框架或启用能力。

依赖固定到本次候选，验证受影响接口和恢复路径。新候选未获验收前保留已生效版本与数据；司南按真实事件处理进度和依赖，不启动定时同步或扫描。
