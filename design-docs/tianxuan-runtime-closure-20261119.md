# 天璇需求执行接口交接（#1581）

依据 main 3e1bb937a8635b2f1acd0f2adfb49b7b1e370210。路径相对仓库根。

## #1551 普通用户入口

| 操作 | HTTP | 消费方式 |
| --- | --- | --- |
| 查询能力 | GET /api/v1/native/entry/capabilities | 读取 mode、identity、scopes、execution_nodes、context_tools。仅展示安装清单支持的范围。 |
| 启动 | POST /api/v1/native/entry/execute | 发送已保存的 requirement、稳定 call_id、非空 scopes，可选同需求的 dependencies 任务 ID 列表。保存返回的 entry。 |
| 回读 | GET /api/v1/native/entry/{entry} | 使用同一租户和用户身份读取 tasks、policy、state、progress、failures。 |
| 交接 | POST /api/v1/native/entry/handoff | 发送 requirement 和回读的 expected_policy，冲突时重新回读。 |

CLI 候选命令为 runs capabilities、runs execute REQUIREMENT --call-id ID --scope SCOPE、runs status ENTRY。候选 execute 接受可选 model，即 capabilities.models 中已安装且可用的配置 ID，CLI 对应 --model。省略时由司南按任务能力自动选取。状态中的 requested_profile 为用户指定配置，tasks[].selected_profile 为任务实际调度配置。供应方 observed_model 需取真实运行回执。工作台来源在 EntryLedger.enqueue 的事务中读取 #1551 的 require_workspace_approval，绑定已确认的三阶段修订、租户、操作者、需求和文档版本；每次执行授权复查原内容摘要及确认。缺少确认读取模块时拒绝工作台来源。优先安装 #1551，再安装 #1581。回执未知时，候选 POST /api/v1/native/entry/calls/status，JSON 请求体为 {"call_id":"ID"}（CLI runs lookup ID）按租户与操作者回读原记录。依据 server/native_entry_api.py，位于 customizations/components/tianxuan 下。

## #1577 安装边界

部署基线见 deploy/README.md 的 Optional native execution package。API 镜像、签名运行时与传输实现由现有天璇构建发布。以构建产物 manifest.json 的候选、来源、镜像和实际归档摘要核对接收对象。安装者分别提供已准入的原生安装清单、可选运行时清单、各自 SHA-256，以及持久化数据库、私有状态与合法节点身份。

节点入口为 customizations/components/tianxuan/sinan-workorders/native_node.py --config ABSOLUTE_PATH。配置包含 database、root、profiles、server、token_file，支持 capacity、process_helper 和 contract_registry。凭据保留在节点。机器协议挂载于 /native-nodes，其 events、execution/{execution}、blob 和 receipt 路径由 native_node_api.py 提供。长期进程使用 serve，--once 仅消费一批事件。

当前基线含本地与远程传输。服务器实际 CLI 安装、长期服务、故障恢复、真实模型回执和版本回退由 #1577 与本单分别核验。#1499 的 resolver v3 在当前基线未准入。安装回执和业务验收仍待取得。

服务器独立节点模板位于 deploy/docker-compose.node.yml.example。以已验证的镜像 ID 启动，由部署者提供可解析的 server 地址、只读安装目录与原节点可写持久卷。反向代理路由归 #1577。节点向 server 基址发起 HTTP 长轮询 GET /native-nodes/events?cursor=N；按事件 GET /native-nodes/execution/{execution}、GET /native-nodes/execution/{execution}/blob/{digest}，POST JSON 到 /native-nodes/execution/{execution}/receipt（上限 9 MiB）。四个调用均使用节点私有文件中的 Bearer，客户端读取超时 35 秒。生产传输使用 HTTPS。此协议无需 WebSocket 升级。

Windows 安装脚本 deploy/install-native-node.ps1 使用当前用户的低权限登录任务，启动 native_node.py --config。Python 和配置文件均使用绝对路径。已有实例、凭据、数据库、已启动调用和配置由原安装者持有。更新前停收新任务，确认已启动操作终态；使用同一持久库和工作目录启动新版本。回退时恢复原已验证代码和配置。登录任务不会在用户登录前执行。

本机独立节点包为 git archive 取自 3e1bb937 的 duobao/native_*.py、sinan-workorders/native_node.py、sinan-workorders/native_worker.py 和 tools/ainative/owned_process.py，保留仓库相对布局。ZIP SHA-256 为 3b12897c67ca91cadc6e9895f15e23a327b05127989d5f404247434723439cf7。生产者 CLI、签名清单和合法身份由安装者提供。真实 Windows HTTP 节点验证使用隔离生产配置，原始观察的摘要、终态与实际用量在 data-collection/tianxuan-runtime-1581-local-cli.json。
