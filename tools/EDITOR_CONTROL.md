# AI 编辑器操作接入

工单：[Issue #133](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/133)。能力目录和执行器与内置 AI Chat 共用，不需要为新页面增加中央命令分支。

## 新页面自动加入目录

编辑器中的 `EditorDock`、`TabContainer` 页面和编辑器窗口内容自动成为页面；其中的按钮、文本输入、SpinBox/Slider、OptionButton 自动按类型声明能力。新增、移除、重排会更新目录，游戏场景树不参与。

先 `find_targets`，再 `describe_target` 查看当前 `actions`；使用返回的 ID，不按页面中文名猜 ID。已有 `scene_tree`、`inspector`、`filesystem`、`project_settings` 等核心 ID 和 `plugin.*` 注册接口继续可用。搜索最多返回 20 项，`registry.truncated` 表示遍历达到上限，应缩小 UI/查询范围。

| 动作 | 含义 |
| --- | --- |
| `open_target` / `reveal_target` | 打开 Dock/窗口，展开父容器并切到对应标签 |
| `focus` / `highlight` | 聚焦可聚焦控件 / 高亮可见控件 |
| `set_text` | `value` 为文本，最大 8192 UTF-8 字节 |
| `set_value` | `value` 为合法范围内的有限数值 |
| `select_option` | `value` 为可选项的索引 |
| `press` | 使用按钮原生激活逻辑 |

写入和按钮操作必须先得到宿主确认，或由用户启用已有“自动执行”开关。确认绑定目标实例和旧值；确认期间换掉控件、改值、隐藏或禁用控件会拒绝执行。隐藏输入应先打开其页面。目录不包含密码输入、AI Chat 的授权/输入控件和确认弹窗，不返回输入框的全部值。

可选元数据（无需集中注册）如下：

- `ai_control_page=true`：将自定义 Control 作为页面边界。
- `ai_control_id="stable_name"`：提供稳定别名 `editor.stable_name`；同一编辑器内必须唯一。
- `ai_control_exclude=true`：排除整个子树，适合凭据或授权界面。
- `ai_control_page_only=true`：仅暴露页面根，排除内部控件。

自动 ID 来自页面布局键和控件路径；稳定名称/布局键可跨重建复用，活动控件重排保留 ID。含自动生成节点名的路径不保证跨启动稳定，应重新发现或声明别名。自绘控件的特殊业务动作需要使用现有插件接口适配，目录不会猜测任意方法或执行脚本。

## 统一路由契约

内置 API、Codex、CodeBuddy 的工具说明已包含自动路由约定。AI 识别用户想操作编辑器时，先发现实际目标，再调用 `route_engine_message`：

```json
{
  "intent": "engine_operation",
  "request_id": "open-project-settings-001",
  "source": "my-agent",
  "operation": {"action": "open_target", "target": "project_settings"}
}
```

多步骤帮助使用现有 `start_guidance` 操作，仍支持预览、开始、前后步骤、观察和确认执行。只含自然语言 `request` 的消息返回 `planning_required` 和规划提示，AI 需要发现目标并用**新 ID**提交声明式操作，不代表已经执行。非 `engine_operation` 消息返回 `not_applicable`，不操作编辑器。

请求 ID 与来源各限 1–96 个 ASCII 字母、数字、点、下划线或短横线；外部来源因宿主命名空间前缀限 87 字符。相同来源和 ID 在本次编辑器会话 15 分钟内只执行一次；相同内容可恢复结果，改内容返回 `request_id_conflict`。不同操作用新 ID，拒绝后不能自动绕路重试。等待确认的请求不会因 15 分钟到期自动执行或删除。编辑器重启会创建新会话；去重不跨重启，断线后先查结果，不把网络超时当作操作失败。

## 本机工具与自建 HTTP Agent

编辑器设置 `ai_chat/editor_control_bridge_enabled` 默认为开启，启动时生效。AI Chat 必须允许本地工具并关闭“仅咨询”。桥接只监听 `127.0.0.1` 随机端口，在当前项目 `.godot/editor/ai_control/<pid>.json` 写入版本、项目、PID、地址、会话 ID、私有随机令牌及路由说明。退出清理自己的发现文件；旧文件由客户端探测并忽略。不要将发现文件交给模型、上传或提交 Git。

本机 Codex/Claude Code 等有命令行工具能力的 AI 可调用标准库客户端，无需安装 Python 包：

```powershell
python tools/editor_control_client.py --project D:/MyProject capabilities --query "Project Settings"
python tools/editor_control_client.py --project D:/MyProject route --message operation.json --wait 60
python tools/editor_control_client.py --project D:/MyProject status open-project-settings-001 --source my-agent
```

`operation.json` 为上方消息。也支持 `--message -` 从标准输入读取，以及 `--operation` 加单个 JSON 对象。多编辑器同时打开同项目时用 `--instance PID`，客户端不会随意选一个。`--wait` 到期仍返回 `awaiting_confirmation`，不会取消或重新执行。客户端仅将本地会话头发送给该项目已验证的回环地址，输出不含令牌。

自建 HTTP Agent 读取同一发现文件，发送 `Authorization: Bearer <token>` 与 `X-Godot-Session: <session>`：

| 接口 | 用途 |
| --- | --- |
| `GET /v1/capabilities?query=...` | 目标目录、工具 schema、自动路由说明 |
| `POST /v1/messages` | `Content-Type: application/json`，请求体为上述消息 |
| `GET /v1/requests?id=...&source=my-agent` | 查询确认和最终结果 |

200 表示结构化结果已返回，202 为等待确认，409 为繁忙/请求 ID 冲突，401 为会话或令牌无效，403 为权限关闭/仅咨询/浏览器来源。超限请求返回 413 或直接关闭连接，Windows 对未读取完的超限请求体可能报告连接重置。以响应中的 `ok` 和 `routing_status` 判定是否真正执行。宿主将外部来源隔离为 `external.<source>`，查询时仍发送原始来源。响应包含 `session`，客户端必须核对；停止、拒绝会返回 `cancelled`。同时最多一个外部确认，不在聊天执行期间插入操作。能力和结果查询不启动聊天或工单。

桥接不接受浏览器 Origin、跨站访问、公开地址、分块传输或 HTTP pipelining；每请求体最多 32768 字节。外部 Agent 不能传入可信确认字段或自行点确认按钮。

## 接入方的自动选择规则

将以下规则放到外部 AI 的系统说明/工具描述中，并提供客户端命令或相同 HTTP 工具：

> 当用户要求打开、定位、高亮、配置或输入编辑器界面时，自动发现当前项目编辑器能力，规划后进入 engine_operation 路由。只使用当前目录声明的动作和目标。根据宿主结果等待确认、查询状态、继续引导；不要声称 pending/planning 已执行，不用代码修改或坐标点击代替界面操作。用户拒绝后停止该操作。

这个选择规则已进入内置通道；外部 AI 需要由其宿主实际接入工具与说明。未接入的第三方聊天不会被本项目拦截。实现不自动改写外部客户端配置、账号或授权。
