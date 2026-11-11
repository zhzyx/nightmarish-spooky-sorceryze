# 引擎通用业务解除 Codex 强依赖

日期：2026-11-12（Asia/Shanghai）。路径基准：仓库根。

用户在当前会话审计全部 Codex 依赖后明确要求“全部执行处理和修复”。当前会话负责实现、隔离验证、独立审查、提交、PR/main 回读和逐项验收；保留用户主动选择的 Codex 后端，不删除兼容记录、不放宽权限、不修改他人在途工作副本。

## 验收与拆分

1. runtime：Windows 缺少 Python/Node/Git/gh 时，通用配置与恢复不需要 Codex、账号或模型推理；保留原请求与回退、验证和治理。清晰失败不能伪装配置成功。
2. assets：本机网格独立使用，不默认选择 Codex 图像；语义网格规划（Godot/Blender）支持明确的非 Codex 服务；共享任务、图像校验、进程等基础逻辑不由 Codex Provider 拥有。保持既有 Codex/Kimi/Comfy 输入、产物、重开和取消语义。二维模型替代复用现有 Comfy，不接管在途 #808。
3. host：macOS 专用外部指令允许经过当前用户显式绑定且身份验证的非 Codex 宿主，保留同用户、进程链、防复用及动作授权检查；不把任意进程放行作为解耦。原生 Codex 派发保留专用适配器，通用工作者不必须经 Codex。
4. integration：逐项回归已选 Codex 与非 Codex 路线；确认核心启动、编辑、运行、构建、Git 交付无新增模型依赖。通用派发公共代码与命名耦合评估迁移兼容，不改历史分支及回执。

父项 #840（provider-independence-20261112），实际 GitHub sub-issues 为 runtime #841、assets #842、host #843；已回读父子关系和四项 intake-only 门禁。每个子项有独立需求文档和验收；共享最终引擎候选的整合由父项唯一负责。原生编辑器、嵌入 Python/GDScript 为实际构建输入；必要候选构建及 headless 探针，不启动用户桌面。目标 Windows x64；macOS 身份改动需平台 CI/真实 macOS 验证，Windows 模拟不能替代该验收。

## 当前调用链及处置边界

| 业务结果 | 当前实现入口 | 判定与处理 |
| --- | --- | --- |
| 自动补齐运行时并重试业务 | gonggong_panel.cpp → run_gonggong_config_agent.ps1 → configure_gonggong_runtime.ps1 | 通用初始化不应需要模型；#841 移除配置代理的 CLI 前置，保留确定性安装、策略和回退 |
| 从图片得到本地模型 | generation_service.py → 网格后端 | 与 Codex 重画图像本属两段；#842 独立服务选择，不隐含先生成图像 |
| 从描述生成 Godot/Blender 资产 | modeling_provider.py / sculpt_provider.py → 规划器 → 本地构建器 | 规划可更换模型；#842 补充通用 API，保留最终参数校验和构建器 |
| Kimi 原生图像与任务管理 | kimi_provider.py → 共用进程、状态、图像校验 | 共享实现被放在 Codex 类型内；#842 提取共用模块，消除类型/导入依赖 |
| 外部桌面宿主发送可信指令 | ai_chat_external_peer.cpp | 旧实现把签名身份固定为 Codex；#843 加入显式可信身份绑定，保留完整权限检查 |
| 普通编辑器模型对话、代理、定时任务 | ai_chat_gonggong.cpp 与 HTTP/Responses/CodeBuddy/Codex 后端 | 已有非 Codex 路由；回归验证，不删除用户选中的 Codex 兼容入口 |
| 并行工作者执行及仓库派发 | tools/godot_parallel/runner.mjs、repository-dispatch/session.mjs | 已支持 workerCommand；共享状态工具位于 codex-dispatch 目录不等于必须运行 Codex，保留兼容和在途认领 |
| 引擎核心、场景、物理、渲染、导出 | core / scene / servers / drivers / platform | 没有统一 Codex 启动门槛；以实际原生编译和 headless 回归核验 |

选择 Codex CLI、Codex 图像或 Codex 原生 Agent 时，该适配器依赖 Codex 属于明确选择的能力依赖，不改成假成功或无鉴权降级。二维图像复用现有 Comfy/Kimi 接口；本任务不承诺没有任何模型/服务也能生成语义图像。

## 新模块构建边界与整合

`editor/SCsub` 的 `Glob("#tools/ainative/*.py")` 自动纳入全部非 test_ Python，连同工作台 GDScript 生成 `editor/ainative/bundle.gen.h`。新增共用模块/API 规划模块是嵌入资源并参与原生构建失效，不能仅以 Python 导入成功验收。宿主接口为现有服务请求、产物路径、状态与取消协议；旧服务 ID 保留作为兼容回退。

外部宿主登记工具属于宿主工具，输入为操作者显式选择的签名宿主，输出为当前用户持有的信任登记；原生编辑器读取登记实施鉴权。撤销登记必须对新请求生效，不将本机注册文件或凭据提交仓库。配置脚本属于宿主工具，C++ 调用参数变化属于原生输入。

实际派发按工具可用槽位分成三个隔离写域。#841 的必要写域追加 `tools/gonggong_runtime_policy.ps1`、`tests/editor/run_runtime_setup.py`；#843 原生测试写域更正为已存在的 `tests/editor/test_ai_chat_external_peer.cpp`。不修改其他工作树；共享候选编译等待所有实现停止写入后执行。

## 在途与复盘

基线 origin/main 1f6ea3e74244275efafc484d7cf324d9feea5c4a。已核对 #828/PR832 项目配置、#808 Kimi Work 图像、#810/PR826 并行设置、PR645 历史配置候选；本任务独立工作树，不接管其发布。合入前重新回读主线并整合真实差异。

复用 godot-build-placement 的实际消费者追踪（嵌入 Python 也需要原生构建）；editor-dependency-handoff 的真实终态与候选字节核验；github-issue-delivery 的失败作业与夸父事故回读。未知模型用量、真实模型质量和未执行平台验收不得记通过。

停止条件：全部关联验收及主线接收可回读后关闭；真实权限、平台或服务阻塞仅挂起相关步骤，其余继续。

## 实现审查、验收分工和最终候选

用户后续明确“暂时不用验收非codex，其他人会验证kimi的能力”。本次不再等待非 Codex 真实推理凭据，模型质量不记为已验收；保留本地协议、真实 Godot 构造器、设置保存重开、失败恢复与既有 Codex 路由回归。macOS 原生身份边界仍须执行可用的平台检查，未执行的真实签名宿主场景如实保留。

用户进一步明确“当前对codex的依赖还是正常要能用的，但是是在用户配置了codex的cli之后”。选择并保存 Codex 服务及有效 CLI 路径后，原有对话、图像和建模适配继续工作；不把安装或发现 CLI 自动视为通用功能的运行前提。首次内置网格采用 local_mesh，既有 Codex 配置仍按原服务恢复。已用本机实际 Codex `0.167.0-alpha.3.2` 经现有 `check_cli` / `check_modeling_cli` 进行只读检查，ChatGPT 登录、图像 feature 和建模预检均通过；未发起真实生成、不读取凭据文件、不代用户修改生成服务设置。

三个子项的独立审查采用交叉责任者：runtime 由 host 实现者 `/root/sinan_ce2e0b89751f97de` 审查；host 由 runtime 实现者 `/root/sinan_c0fe010abbc02e98` 审查；assets 由 host 实现者和父会话审查。已修复并复核：GitHub 后检查异常导致配置回执丢失、同一签名身份角色提升被 helper 遮蔽、新模式非法设置覆盖有效配置、Codex 指纹遗漏提取后的公共模块。父会话修正原生测试筛选遗漏 `[Editor][AIChat][ExternalPeer]` 的问题，API 来源与 UI 实际构造器名称也已核对。

本次统一以父 #840 的集成候选发布三个子项，保留各自工单、设计、测试和结束回执。三个实现已在同一编辑器候选集成，嵌入脚本、配置入口和外部指令身份核验共享原生验收；发布时绑定这个完整源树与二进制，避免把集成二进制的证据误用于另一个拆分源树。一个 PR 不代替各子项验收，未满足的平台项不随其他项关闭。

已快进整合最新 main `c811b583d4f709f697161280ed285c08793c90ef`（上游蓝色波浪图标改动，无本任务写域冲突）。Windows MSVC 14.5 / SDK 10.0.26100.0 构建成功；原生 AIChat 88 项、1598 断言全部通过。最终输入摘要 `dfc5be72552e942a713b6316d97f79172a874bc52b12a29cf7bb7e1171a72b92`；实际编辑器 SHA-256 `343ee5ade57e3861cbc5809d1c0dab77439dd53a809360f95c68ba244ad0421d`。构建过程观察到马良 bundle 重新生成、插件重新编译和重新链接，确认新增 Python/GDScript 是实际嵌入输入。

验证纠偏：活动构建日志最初放在工作树中，被保守缓存识别为变化输入并拒绝发布缓存；移到工作树外，固定生产输入后重新构建成功。此前失败不算构建通过，也未修改缓存校验来绕过拒绝。Git 直连网络失败通过本机现有系统代理、仅进程级 Git 配置恢复；TLS 校验未关闭，远端 main 与 GitHub API 对齐。具体发布与候选实测汇总见 `data-collection/provider-independence-840.json`。

首次签发 PR #851 的静态检查 run 43111628663 在 file-format 步骤失败：该步骤将已被不可变学习事件引用的 `data-collection/provider-independence-840.json` 从 CRLF 改为 LF。沿用仓库已有逐文件证据保留规则，在 `.pre-commit-config.yaml` 仅为此文件增加精确排除，与已有 `.gitattributes -text` 一致；原证据 blob `e5bc28da4b99f780c243ed78e41ee6649daf38c2` 不变，其他文件的格式检查和证据完整性门禁继续执行。此修正不改变任何生产实现或测试代码。故障与定向复验关联 #844，后续候选以实际新 CI 回执为准，旧失败不记通过。

补充真实 Codex 业务验证：在独立临时任务目录明确指定本机现有 CLI 和本次构建的编辑器，真实模型返回蓝色桌面与四条圆柱桌腿的五部件规划，Godot 构造器生成有效 GLB（576 顶点、780 三角面、12928 字节），重新实例化 Provider 后同一意图直接恢复 succeeded。产物 SHA-256 为 `08842b82afde8c7df176718522882ed29ff62f55e9a207780862d53968f7266c`。未改用户保存的服务配置，未调用非 Codex 服务；具体几何与 CLI 版本见 `data-collection/provider-independence-840-live.json`。此前只读检查边界保留为历史记录，本条是后续实际生成证据。

PR #853 的静态检查通过；Windows run 43113185663 在编译前发现 `tools/test_build_gonggong_editor.py` 仍断言旧的 AIChat 筛选参数，已与扩大到 ExternalPeer 的生产筛选同步。本地原步骤全部 29 项（构建封装 2、产物 7、进程来源 20）复验通过，仍需后续精确候选 CI 的实际回执，不将本地通过冒充远端成功。

主线后续由 PR #852 推进至 `5903fb96fee73c0d68967bf953abcd0a5d265fcb`，包含编辑器布局和项目模型配置。唯一内容冲突在 `GongGongPanel::run_setup`：上游把旧配置代理的 Codex 模型参数改为读取项目设置，本任务已移除通用配置代理的模型调用及参数。整合保留该段删除，同时保留上游普通对话的项目配置、布局和设置修改；用户主动选择的 Codex 对话/生成路由不受该删除影响。整合候选重新构建并复验，历史二进制证据只支持其各自原始输入。

macOS 补充真实签名链验收工具和对应 workflow，详见子项设计。独立审查修复验收脚本清理异常可能跳过进程终止和错误后仍返回成功的问题；清理各项独立执行、失败统一否决成功。原生鉴权未被这些测试工具修改，平台结果以实际运行回执为准。
