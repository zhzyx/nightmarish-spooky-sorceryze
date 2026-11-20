# 游戏配置接口 v1

父需求 #1671。路径以仓库根解析。前后端和 Godot 按此契约并行实现，最终真实联调验收。

## 配置快照

```json
{"id":"doc_...","title":"游戏项目","version":1,"features":[{"id":"combat","name":"战斗","description":"战斗数值","document_id":null,"entries":[{"id":"damage","name":"攻击伤害","kind":"parameter","type":"number","value":10,"default":10,"description":"单次基础伤害","min":0,"max":1000}]}]}
```

feature/entry ID 匹配 `[A-Za-z][A-Za-z0-9_-]{0,63}`，feature ID 项目内唯一，entry ID feature 内唯一。显示名可改，ID 不随显示名改变。entry kind 为 parameter/content；type 为 number/integer/boolean/string/enum/json/reference，enum 附 options 字符串数组（每项非空、单行、最多200字符且唯一，逐行编辑不改变选项），reference 的 value/default 为 `{feature_id,entry_id}` 且必须指向同一快照中的条目。可选 min/max 仅数值；value 与 default 均受相同校验。description 为字符串。document_id 是可选文曲说明文档 ID。

项目存为文曲 kind=game_config 的文档，正文含唯一 `game-config` fenced JSON `{schema_version:1,features:[...]}`。普通文档更新/恢复同样严格校验，不能绕过合法性检查。项目文档权限即配置权限，历史复用文曲，所有写入使用版本条件。

## HTTP（沿用天璇会话、同源 Cookie 或 Bearer）

- `GET /api/v1/game-config/projects` → `{projects:[{id,title,version,feature_count,entry_count}]}`。
- `POST /api/v1/game-config/projects`，`{title,features:[]}` → 完整快照，201。
- `GET /api/v1/game-config/projects/{id}` → 完整快照。
- `PUT /api/v1/game-config/projects/{id}`，`{title,features,expected_version}` → 完整快照。409 保留本地输入，重新读取/合并后才可重试；400/422 无有效变更。
- `GET /api/v1/game-config/projects/{id}/clients` → `{clients:[{id,name,version,status,error,last_seen}]}`。status=pending/applied/failed；仅列仍连接且心跳有效的游戏消费者，空列表表示没有在线游戏；version 为实际应用确认版本，不是接收版本。
- `GET /api/v1/docs/{id}/versions` 与 `POST /api/v1/docs/{id}/versions/{version}/restore`（`{expected_version}`）使用既有文曲契约，恢复后配置版本单调递增。配置正文可在 `/docs/{id}` 协作，feature 文档可独立链接。

## WebSocket

`/api/v1/ws/game-config/{project_id}?kind=editor` 或 `kind=runtime`。不把 token 放 URL。浏览器复用生产 Cookie，普通会话可在连接后发送首条 `{type:"subscribe",token:"...",name:"客户端显示名"}`；Godot 用 `Authorization: Bearer ...` 握手且首条 subscribe。兼容测试 actor 仅服务端明确开启时可用。首条认证有时限。

服务端向所有已授权连接发送 `{type:"snapshot",project:<完整快照>}`，初连、保存、恢复或重连均以权威文档版本为准；持久版本检查支持多个服务进程看到相同数据库的变更。客户端发送 `{type:"ping"}` 心跳，服务端 `{type:"pong"}`。服务端定期推送 `{type:"clients",clients:[...]}`，消费者连接失效不保留为在线。

runtime 实际完成应用后发送 `{type:"applied",version:N}`；拒绝应用发送 `{type:"failed",version:N,error:"简短错误"}`。只接受该连接已经发出的版本；未收到/未来/倒退版本不能产生成功状态。新版本到达后旧确认不表示最新配置已生效。未确认时 pending，断开后从在线列表移除。密钥不存进游戏资源/日志/版本库，使用运行时环境提供。

Godot 客户端提供配置快照信号，业务代码验证并应用后显式调用 acknowledge(version)，不得在收到网络包时自动声称已应用。为示例提供按ID获取、原子替换快照与最后有效值保护；业务验证失败不替换有效值。Web UI在字段完成编辑后自动保存（失焦/选择，JSON需合法），多人冲突保留草稿并明确处理。项目/feature/条目创建使用表单，不要求用户写JSON；JSON类型条目除外。

专用配置表单仅替换文曲正文的唯一 `game-config` 块；块外共同编辑说明逐字保留，版本冲突仍按整篇文档版本拒绝。Godot 客户端接收缓冲为2MiB，覆盖1MiB配置及信封；隔离联调验证90万字节中文内容完整接收。

所有数值（包括 JSON 嵌套值、默认值、min/max）必须有限；整数值限于 ±(2^53−1)，避免 JavaScript/Godot 往返丢失精度。超出范围的内容 ID 应使用 string。前端在发送前拒绝不安全整数，服务端在任何文档写入入口重复验证。
