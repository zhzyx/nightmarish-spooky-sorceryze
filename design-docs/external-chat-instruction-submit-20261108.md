# 可信外部宿主原子续接聊天指令

稳定需求 ID：external-chat-instruction-submit-20261108。真实 Issue：#554。

用户要求“帮我输入”使用引擎命令，发现未支持的界面另行修复，避免鼠标劫持。原 #483 验收中 chat_compose 与 chat_send_request 已路由，但分别强制界面确认，不能通过命令完成一条已授权续接指令。本任务只改独立候选，不触原6ef业务源、用户应用、真实历史、全局配置或生产桥；首次外部维护 bootstrap 与后续原生自主编译分别报告。

## 事实与可信边界

现有 TCP bridge 的 loopback、会话与0600 bearer不能证明外部进程身份；内部模型的读取及已授权命令与编辑器同用户，不能用 source 字符串或另一个同用户可读token授予免确认权限。原有所有 HTTP chat_* 人工确认保持。

macOS新增专用短路径AF_UNIX通道，只接受内核 getpeereid/LOCAL_PEERPID/LOCAL_PEERTOKEN 身份；双快照核对进程出生、父链与代码身份，先拒当前或任何已知Godot进程，完整链抵达有效Apple信任的官方Codex桌面标识com.openai.codex、Team2DC432GLL2才允许。中间进程限定为有效Apple平台代码或已知同Team OpenAI代码；adhoc、未知、脱父、PID重用或不稳定链拒绝。新trusted CLI使用Apple系统Python，任意venv Python不宣称支持。其他平台明确unsupported，无弱回退。

Socket建立在自有0700、短、本机目录，禁止symlink替代；连接客户端必须显式指定已观察的引擎PID，通过内核peerPID及前后出生复核服务器身份，不信任可写discovery里的PID。文件不提供新增授权secret。

## 最小实现

复用现有route幂等与持久不确定性/结果日志，只增加chat_submit_instruction：新UDS可信入口授予不可从JSON获得的C++能力；TCP及内部模型调用均拒该动作。每条提交严格匹配当前顶层父conversation/generation/snapshot、原候选owner/Issue/request、draft/attachments/queue期望hash及既有工具和自动执行授权；咨询、未知owner、恢复/构建/外部审批在途等状态失败且不覆盖草稿。通过后同一主线程原子设输入并调用正常_send，不代写history、不跳过steering/排队/工单流程。request_id重复只回原持久结果，不重发。新增入口不提供登录、凭据、权限开关或审批动作。

## 验收

1. 真实OS peer与代码签名正例、Godot祖先/未知签名/脱父/不稳定身份负例按实际执行范围留证。
2. 私有_sc_原生编辑器经专用生产socket提交→真实receipt→正常模型/消息循环；重复、身份/上下文/草稿/队列漂移、权限/咨询/子会话及TCP/内部工具拒绝均可核。
3. 客户端内核核对显式引擎PID与出生，不发送给被掉包的socket；无真实用户App/历史/配置修改。
4. 必要编译、独立审查、正式门禁、精确候选CI/main及本单权威终态回读；原483生产业务与安装责任保持父任务。

## 命令入口与实际验证

从已授权Codex桌面的执行工具直接调用Apple系统Python，不能用未知/adhoc解释器包裹此可信调用。显式引擎PID必须来自调用者已观察的目标进程；discovery只定位socket，客户端在发送前核对内核peer PID和前后出生身份。

```text
/usr/bin/python3 tools/editor_instruction_client.py --project PROJECT --instance OBSERVED_PID context --wait 30
/usr/bin/python3 tools/editor_instruction_client.py --project PROJECT --instance OBSERVED_PID submit --text-file INSTRUCTION_FILE --expected CONTEXT_FILE --request-id UNIQUE_ID
/usr/bin/python3 tools/editor_instruction_client.py --project PROJECT --instance OBSERVED_PID status UNIQUE_ID
```

context只给来源/队列/草稿hash及instruction_available、blocked_reason；等待是只读查询，调用者仍需核对目标owner和available。提交结果instruction_submitted只代表进入正常宿主发送流程，business_completed始终false；异步intake、模型、工具与最终业务须分别回读。相同ID只查回原结果，改变消息不得复用旧ID。非空草稿、IME预编辑、当前父关闭确认与未解决的恢复/权限状态均拒绝，取消关闭确认不残留阻断。

最终main234e37基线上，作者与非作者分别用同一436a29a5原生raw通过39项私有隔离验收，包括真实OS身份正反例、TCP/内部缓存冒用拒绝、数值/键集与owner竞态、草稿/权限、正常steering、持久重启不重发和写失败无发送。peer单元5/47通过；IME仅静读/编译保护，不声称实际输入法交互。原失败记录保留，详见本需求公开validation及独审相对路径证据。首次维护bootstrap与原native最终自编译/原入口安装严格分开报告。
