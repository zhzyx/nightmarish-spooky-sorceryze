# 天璇服务端

## 当前实现

`tianxuan_core.py`：标准库 + SQLite 的领域核心，可独立测试，不依赖网络与第三方包。

覆盖：注册/登录、文曲文档与版本、需求文档、司南工单与状态机、工单评论、进度同步、事件流、AI 工具入口。

```sh
python -m unittest discover -s customizations/components/tianxuan/server -p "test_*.py" -v
```

## 目标技术栈

- FastAPI + PostgreSQL（生产）；SQLite 仅用于测试与嵌入式验证。
- SQLAlchemy 或 asyncpg 适配器；领域方法保持不变。
- Next.js 前端位于 `apps/tianxuan/`（后续切片）。

依赖在独立虚拟环境中安装，不污染 `project/runtime/python`；`requirements.txt` 在适配器落地时补齐。

## AI 工具面

`doc.create/update/read/list`、`requirement.create/plan`、`issue.create/transition/list`。
写工具使用 `dispatch_tool(actor, name, payload, call_id="稳定调用标识")`；`call_id` 也可放在 payload，两个位置同时提供时必须一致。六类写工具 `doc.create/update`、`requirement.create/plan`、`issue.create/transition` 共用持久回执。只读工具无副作用，不接收调用键。破坏性动作仍需平台策略门禁。

- 调用身份为租户、操作者、工具名、键类别和 `call_id` 的组合。相同身份和规范化业务输入返回第一次成功调用的完整结果快照，不再创建业务行、版本或事件；不同输入返回 `VersionConflict` / HTTP 409。键不能为空或纯空白，最长 256 字符，不做截断或静默降级。输入包含实际方法支持的全部字段和默认值，字典键排序，工单列表顺序与重复次数保留；未知工具参数、未知工单字段和相关 HTTP 模型的未知字段均拒绝。
- 一次新的有意操作使用新的调用键；同一操作的重试保留原键及输入。键没有自动过期。回执保存在当前 SQLite 的 `tool_receipts` 表中，进程重开仍有效。读取旧回执前重新验证当前角色、租户、对象范围和文档写权限；删除对象或撤销权限不会通过回执恢复访问。
- 没有显式键的 `dispatch_tool` 使用规范化完整有效输入的 SHA-256 作为 `legacy-v1` 身份，其命名空间与显式键隔离。重复提交相同内容视为重试；若要有意创建两份相同内容，通过不同显式键表达。普通 Python/HTTP `create_doc`、`update_doc`、`create_issue`、`transition_issue` 在省略调用键时保留原人工操作语义；相同内容的两次人工文档创建仍产生两份文档。
- `create_requirement` 与 `plan_tickets` 的 Python/HTTP 入口保留旧的默认幂等契约，无键也使用 `legacy-v1`。需求 `request_id` 仍是 `(tenant_id, request_id)` 业务唯一标识：不同租户允许相同值，同租户内容冲突稳定返回 409。不同调用键不会绕过业务唯一约束。
- 无键追加拆单复用同一需求的父工单，并按 `title/type/acceptance/priority/body_md` 完整规格及重复次数复用子工单；新增规格会追加子工单，同标题不同验收不会返回旧内容。同次输入内两个相同标题/规格的条目保留两张单。带显式键的不同计划创建各自的新子工单并复用需求父单；同键重试返回原计划快照。
- 建表迁移仅新增 `tool_receipts`，不重写历史业务行、不伪造过去调用回执。迁移后无键计划首次回读完整匹配的历史树会登记回执，无新增工单时不追加计划事件。其他历史普通工具调用没有可还原的原始键：调用方须从新操作开始保存键，不得把旧请求臆造为已留存回执。
- 回执、业务对象、版本、完整父子树、进度与事件在同一调用事务中提交。SQLite 写锁在查回执之前取得，独立连接/进程也只执行一次。失败会回滚本次调用的所有写入且不留下成功回执，可用原键重试。嵌套调用使用 savepoint，不能提交或回滚调用者先前合法写入；要将需求创建与拆单合成一个原子工作流，必须由外层领域事务包住两次调用，两个独立 HTTP 请求不共享事务。
- 已知需求唯一键冲突为 HTTP 409；锁等待失败为 `StorageBusy` / HTTP 503（同键重试）；其他 SQLite 故障为 `StorageError` / HTTP 500 的固定消息。原始错误通过异常 `__cause__` 保留给诊断，不泄漏到响应，也不把无关约束错误假装成需求冲突。

现有文档创建/更新、需求创建/拆单和工单状态迁移 HTTP 请求模型接受可选 `call_id`。CLI `docs create`、`requirements create` 通过 `--call-id` 透传同一个字段；省略选项保持兼容。`issue.create` 目前只有领域/工具入口，没有独立 HTTP 创建路由。当前 Web 需求客户端为读取接口，文档编辑使用既有 merge 流程；这次没有扩大到文档评论、共享、merge 或 Git 的独立副作用契约。

## 安全与边界

- 密码使用 PBKDF2-SHA256 + 随机盐；不存明文。
- 身份与权限由宿主/平台校验，领域层只做范围检查。
- 事件用于谛听回执与审计；不把凭据、提示词原文或本机路径写入事件。
