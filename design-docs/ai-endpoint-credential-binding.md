# AI API 凭据受众绑定

<!-- gonggong-request:ai-endpoint-credential-binding-20261113 -->

需求 `ai-endpoint-credential-binding-20261113`，工单 [#980](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/980)，父目标 [#978](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/978)。本文中的文件路径均相对仓库根目录。

## 问题与契约

项目恢复自定义 endpoint 后，原生面板此前无条件填写环境凭据，模型枚举、连接验证及普通请求会直接发送该字段。非空字段还会阻止本项目系统凭据库恢复。合成 loopback 对照已复现错误携带 Bearer；没有真实凭据泄露证据。

原生面板现在同时维护凭据来源、受众和当前字段的内存摘要。受众为完整服务地址，仅去除支持的 `/chat/completions` 或 `/responses` 后缀；同服务的这两个协议可共享凭据。不同主机、端口、服务路径不共享。URL 必须是 HTTPS 或带显式端口的本机 HTTP，用户信息、查询参数、片段、换行不能建立绑定。凭据或摘要不写入项目配置。

- `OPENAI_API_KEY` 只在 `https://api.openai.com/v1` 对应的官方服务初始化。`OPENAI_BASE_URL` 不授予向自定义服务发送 OpenAI 环境密钥的权限。
- `GODOT_AI_API_KEY` 需要同进程的 `GODOT_AI_API_ENDPOINT` 明确指定匹配的服务。单独的 key 不再授权从项目恢复的任意地址。该变量是完整 endpoint，支持上述两个协议后缀。
- 手动输入显式绑定当前地址，即使其字节恰好等于某个环境凭据也不靠字节比较猜测来源。改变服务地址清除旧绑定；未发送 `text_changed` 的程序化修改仍会被统一读取检查拒绝。
- 私有存储恢复必须带当前期望 endpoint，不能覆盖有效的手动/环境凭据。原有 epoch、完整配置签名、取消与序列化保存机制保留。被拒绝的环境 key 不会阻止自定义 endpoint 的私有存储恢复。
- 模型列表、验证、普通推理及模型库导入均使用同一原生 accessor。普通请求冻结受众并在每个实际 HTTP 发送前复核，包括工具继续轮。已使用的 HTTPRequest 保留禁止重定向及 generation 防迟到机制。
- 子工作者复制原来源与受众，不能因复制密钥字段而重新授权旧 key；开始消息时重新读取所有者的有效绑定。普通会话模型选择归属不在本修改范围，#971 的在途实现保持独立。

允许无 key 的本机服务沿用既有匿名请求行为；拒绝绑定表示不发送 Bearer。

## 构建边界与验证

本次修改为既有原生编辑器及构建内嵌 GDScript，必须重新构建；没有新独立模块或热替换组件。隔离候选用 `platform=macos target=editor dev_build=yes arch=arm64 vulkan=no accesskit=no` 构建。宿主缺少 MoltenVK/accesskit 依赖，因此只声明 headless 验证，不声明图形版本验收。不会替换当前运行应用；回退使用原先已验证的二进制及对应源版本。

`tests/editor/run_credential_binding.py` 在私有、自包含编辑器副本中注入随机合成 key，所有实际模型请求仅送到 loopback。覆盖不匹配 OpenAI base URL、无受众/错误受众/匹配受众的 Godot key、官方 OpenAI 绑定、手动输入、静默及显式地址变更、绑定恢复、模型 GET、探针 POST、普通消息、延迟响应后的工具继续轮和实际子工作者。官方绑定检查在 CLI 后端启动，再同步读取并改回 loopback，期间不让事件循环启动官方 HTTP 请求。报告只保留授权匹配布尔值，不记录请求头、原始 key 或提示词内容。

既有 `run_session_memory.py` 验证保存、跨项目隔离、重启恢复、异步取消、迟到恢复不得覆盖手动输入、不可用存储与清除记录。`test_session_credentials.py` 使用假系统库；`run_runtime_config.py` 使用离线 CLI。原始本机日志保留在忽略的 `bin/` 中，提交证据见 `data-collection/ai-endpoint-credential-binding-980.json`。

## 验收与交付

合成请求及控件检查是本次业务验收依据；不使用真实账号或付费推理。独立审查、正式门禁、提交、CI、main 回读及工单关闭由接收责任者继续。保留候选、日志和工作树直到交付核验完成，不抢占其他工作树或当前编辑器。

## 独立审查后的修复

独立审查发现并复现记忆层仍按完整存储句柄清除同服务Chat/Responses凭据，现由原生受众统一负责内存失效；原存储句柄兼容保留。新增endpoint及backend0↔3回归，同时保留真实在途保存切换测试。未绑定GODOT环境key的连接状态和设置tooltip提示匹配GODOT_AI_API_ENDPOINT、重启或手动输入。四阶段记忆回归及五组绑定回归重新通过。

CPP_CODING_STANDARD.md v1.1要求新增函数Allman，而旧全局formatter仍Attach。独立review认可两个最小formatter兼容区块：dock中六个新增凭据函数、OpenAI helper中一个新增受众函数。区块外原有代码继续由clang-format22.1.5检查，区块内七函数由独立审查核对项目新规范；不改变全局规则或CI，未批量格式化旧代码。
