# #896 实际依赖放行证据

来源为 Issue #896（父 #773、故障链 #807），稳定需求 `editor-dependency-preflight-evidence-20261112`。只保留本次真实执行事件；旧批次缺失的记录保持 unknown。

已有 native Godot 宿主扩展，不新增模块。原生输入是 `editor/docks/ai_chat_sub_agents.cpp`、`ai_chat_dock.h`，由现有 editor SCsub 编译；独立宿主输入是 `tools/godot_parallel/runner.mjs`。宿主接口仍是私有 acceptance-current request/result 和现有 parallel request/registration。回退恢复前一已验证二进制和 runner，保留证据与原验收，不能从证据重建 live owner。

真实 current 成功时，宿主保存收到的原始响应文本、发送的请求文本、nonce、actor、批次 token 和实际观察时间。文件位于 EditorPaths cache 下 `gonggong-dependency-evidence/<batch-token-sha256>/`，路径基准为本机编辑器缓存，不进入 Git 公共数据。每条 current 文件最多 32 MiB，每批最多 256 文件和 256 MiB；不自动清旧证据。串行派发预留实际开始链接空间，并有 64 MiB 单条上限。批次满额只挂起该批次，新授权批次使用新命名空间；保留原件、导出审查后由操作者管理存储，再经真实继续/重验事件恢复，不静默删除或重绑缺失引用。

活内存只保存原文件路径、字节摘要和 nonce，消费时重新核对。parallel 的真实派发 request 与 worker registration 保留逐项 decision、verified response 和 current 引用；命令参数绑定实际 request 原始摘要，runner 在注册前核对引用和绑定。串行派发在开始前保存同类来源，真实 `_design_turn_started` 保存 generation/conversation 的开始链接。prepared 与 started 是不同事实，开始链接写失败明确报告未留证。

只读审查从既有 registration 的 `dependency_preflight` 和 `dispatch_request`，或子会话的 `dependency_dispatch`，取得原路径和摘要，使用既有 read_file 分段读取。先校验原字节摘要，再解析 request_json/response_json、逐项 decision 和 candidate；这些文件是执行来源而非业务验收。包含本机路径的私有原件不公开，公开验证只给相对路径、摘要和实际结果。不包含模型聊天或凭据。

召回 `editor-dependency-handoff/bind-consumer-release`：适用于真实上游结果驱动下游；运输完成、过期候选及冷历史都是反例。保留现有 live reviewer、source/generation、权限、原验收项、候选与历史持久化检查。磁盘文件永不写回这些 live maps。验证覆盖真实 native parallel、串行、stale、权限拒绝与冷恢复，以及 runner 对缺失、篡改、nonce/候选错绑和大小拒绝。严格构建与原生运行实测另存 `bin/896-validation`；其本机失败原件保留，公开结果由证据清单承接。正式安装真实项目复验、独立审查、门禁/CI/main 由父责任者继续。
