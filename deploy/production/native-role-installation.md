# 三角色安装候选

在目标运行时的实际挂载路径，用该机受信的 Python 3.11+ 执行以下命令。输出目录必须尚未存在，其父目录由部署负责人控制。Linux 与 Windows 共用相同参数。

    python -B deploy/prepare-native-role-installation.py inputs.json /absolute/path/to/generation-B

输入 JSON 包含三个对象。

* `installation` 提供 v2 production 的 identity、principals、scopes、complexity、catalog，以及已批准的 checker 和 dispatcher 命令。files 提供这些命令、可执行文件和其他外部输入的绝对路径及 SHA-256。生成器补齐角色命令与本仓库实际执行树。
* `runtime_inputs` 提供 remote 节点描述与 context 策略，沿用 native_entry_context.RuntimeInstallation 的结构。节点安装指纹取自目标机 NativeWorker.installation，节点包指纹取自实际 native_node.py，绑定租户和实际签发的节点凭据摘要。
* `roles` 包含 planner、producer、reviewer。每项提供 identity（Linux 为 uid:数字，Windows 为账户 SID）、address、port、server_name、ca_file、journal 和两个对象 server_tls、client_tls。每个 TLS 对象含 certificate_file、private_key_file 与证书 DER 的 certificate_sha256。地址应为进程实际绑定且其调用方可达的固定内部地址。生产者另需 worker_root 和 registry，与实际节点及工单登记使用的挂载一致。

每个角色的 broker_inputs 包含 template、framework、state、key_file、authority_ref，可按协议加入 context_transport 与 catalog_bindings。另一种输入为已有的 broker_file 与 broker_sha256。template 必须是目标机以真实本机 CLI 核验的 host-http 计划，含其 evaluation 证据。producer 的 catalog_bindings 将目录模型逐一映射至已评估的 profile ID。框架包包含该 reviewer 版本的独立审查与批准。所有文件引用使用本机绝对路径。凭据字段仅填写部署方预置的路径或协议规定的摘要。

生成成功后可回读 installation.json、runtime-inputs.json 和 services.json。部署人将安装代中的配置和执行树设为管理员所有、角色只读，为每个角色单独授予自己的 signer、TLS 私钥和状态目录权限。API 账户读取 planner/reviewer 的客户端凭据，节点账户读取 producer 的客户端凭据。保持每角色 journal 在升级及服务重启之间持久。按 services.json 中每个参数数组，在相应的独立 UID 或 SID 下启动服务。按部署文档通过正常入口回读节点、执行、交付及原请求恢复，记录候选文件指纹。切换失败时恢复上一已验收代的配置绑定和受管服务参数，核对在途工单与原证书世代，再恢复接单。每次新生成使用独立目录；缺少目标机评估或返回非零时，保留已有活动代。
单文件 text 范围的 checker 可使用部署目录下的 check-native-text.py。将其绝对路径、Python 路径及实际摘要写入 checker 命令与 files。
## 普通执行状态与模型用量

登录后通过 `GET /api/v1/native/entry/{entry}` 回读本人的执行。生产任务的 `tasks[].model_calls` 依次列出固定生产者日志中已收到的调用；任务 ID 和 `call` 序号共同定位一次调用。旧回执中没有逐次证据时，该字段为 null。任务顶层 `usage` 和 `observed_model` 保留最后一次调用的读法。

规划和审查记录在 `role_calls` 中。一次联合审查在所有参与工单中使用相同的 `call_id`，首个工单的 `usage_attribution` 为 `original`，其余工单为 `reference`。跨工单统计按调用 ID 去重。供应方报告的 `last` 和 `total` 分别保留逐次值和累计值。未报告的数值、公开展示范围之外的模型名以及标准化用量均为 null。升级保留原角色日志、工单数据库与原始恢复凭据。

Linux 部署可使用预置持久挂载下的绝对路径配置 worker_root、registry、state 与 journal。API、节点和角色进程应按各自挂载视图核对实际绑定，再生成该机安装代。

## 本机外部 Agent 提议接口

已安装的独立进程可作为 producer 模板中的 `local-agent-proposal` profile。profile 字段为 id、model、protocol、port、peer_sha256、agent_file、agent_sha256、ca_file、certificate_file、private_key_file、timeout_seconds、max_context_bytes、output_token_limit（值为 unsupported）和 evaluate 生成的 evaluation。外部 Agent 的 broker_inputs 同时提供受信的 python 与 node 绝对路径。文件指纹、TLS 证书及评估绑定的端口变化后须更新候选。

部署人用独立的低权限账户运行已审核的 Agent 程序，将其服务端私钥限定给该账户，将客户端私钥限定给 producer。服务端仅监听 127.0.0.1 且校验客户端证书；服务端证书的 IP SAN 包含 127.0.0.1。由部署人在受管进程启动记录中核对实际可执行文件及依赖。客户端在发送请求前核对本地安装文件与 TLS 对端指纹。平台不负责启动或安装第三方进程。

Agent 在固定的 `POST /proposal` 接收 UTF-8 JSON，字段为 request_id、task、context、write_allowlist 与 acceptance。请求体上限 131072 字节。Agent 应保存 request_id 与请求体 SHA-256 的关联，用于核对未知回执。响应为带 request_id、input_digest、summary 和 files 的 JSON 对象。input_digest 是收到的请求体原始字节的 SHA-256；files 每项仅含 path 和 content，路径须命中传入的允许列表。每个文件上限 131072 字节，整个响应上限 524288 字节。结果回到已签名的生产者，由现有校验、独立审查和发布流程处理。Agent 没有工具调用、路径选取、发布或平台凭据接口。当前协议支持单步、完整有界文本输入；模型和 token 用量在对端未报告时保持未知。

先用 evaluate 对该实例真实请求和回执做代表性评估，再由有权人将精确安装加入候选。测试 Agent 的回执仅证明该接口路径。具名第三方实例仍需其自己的评估、安装及身份准入。
