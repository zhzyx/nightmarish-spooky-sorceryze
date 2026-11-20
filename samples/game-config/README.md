# Godot 实时游戏配置示例

对应子工单 #1673，接口见仓库根 `design-docs/game-config-api-20261120.md`。这是独立 Godot 4 项目，通过现有引擎的 `WebSocketPeer` 消费天璇已认证的配置服务；不需要修改或重编译引擎。当前实测为 macOS arm64、仓库 Godot 4.8.beta 可执行文件，其他 Godot 4 版本及平台尚未实测。

## 启动示例

先在游戏配置页面创建项目和 `combat` feature，增加数字条目 `damage`，默认与当前值为 `10`，约束 `0..1000`。复制项目 ID。由运行环境的凭据管理方式注入 `TIANXUAN_TOKEN`（有该项目读取权限的天璇会话 Bearer token），不要写入脚本、场景、导出资源、命令行参数或日志。

从仓库根运行，Godot 可执行文件路径按本机实际位置替换：

```sh
export GAME_CONFIG_URL='https://your-tianxuan-host'
export GAME_CONFIG_PROJECT_ID='doc_your_project_id'
godot --path samples/game-config
```

局部开发服务可使用 `http://127.0.0.1:端口`，跨网络使用 HTTPS/WSS。客户端在握手头提供 Bearer，首包发送 `subscribe`，URL 不含 token。每 10 秒发送心跳，断线后从 1 秒开始指数退避，最长 30 秒；重连重新获取并确认权威快照。关闭节点前调用 `stop()` 可停止重连。状态信号区分 `connecting`、`connected`、`reconnecting`、`stopped`、缺少凭据和无效地址；`connected` 仅代表传输连接，是否应用以版本确认与服务端回执为准。

页面改变伤害为 `20` 后，运行示例显示新版本和数值，无需重启游戏。示例游戏额外限制伤害不超过 `100`，因此服务合法值 `900` 会被游戏拒绝；保留最后有效伤害与版本，并向服务报告失败。再改为 `30` 会恢复应用。项目历史恢复会作为新版本推送。

## 接入实际项目

复制 `game_config_client.gd` 到自己的 Godot 4 项目，实例化为节点，在 `snapshot_received` 信号中实现游戏自己的全部验证和原子应用，再显式调用 `acknowledge(snapshot.version)`。失败调用 `reject(version, 固定简短诊断)`，保留全部有效游戏状态。示例实现见 `example.gd`。

- `value_in_snapshot(snapshot, feature_id, entry_id, fallback)` 读取候选值；稳定 ID 不依赖显示名。
- `get_value(feature_id, entry_id, fallback)`、`get_snapshot()` 只返回已确认快照的深拷贝。
- `applied_version` 是本实例实际应用版本；收到网络包不会自动确认。确认发送失败时本地已经应用，重连后仍须重新处理候选并确认。
- 业务处理应同步完成验证与原子应用。若业务需异步加载资源，必须在应用前确认候选仍是最新版本，避免过期工作覆盖新配置；本示例未提供异步事务协调。
- 一个客户端节点绑定一个项目。改连其他项目会清除本地已确认快照。首次连接前游戏使用自己的安全默认值；本示例为 `10`，不会把未连线当作成功应用。

服务端负责完整配置定义、约束和引用合法性，客户端增加结构与版本保护；游戏仍负责该配置对自身机制的适用性。配置只影响显式使用这些 ID 的游戏代码；硬编码或需要重建的资源不会自动改变。未提供真实游戏项目或生产部署接收，因此此样例验证不能代替实际游戏接入验收。桌面/原生目标可使用握手头；浏览器导出不支持相同自定义握手头路径，未在本样例支持范围内。

## 后台验收

在装有 `customizations/components/tianxuan/server/requirements.txt` 依赖的 Python 环境，从仓库根运行：

```sh
python samples/game-config/tests/run_headless.py --godot /absolute/path/to/godot
```

脚本启动真实 FastAPI/uvicorn 与独立 SQLite，在随机本地端口注册临时账号、创建会话和项目，通过 HTTP 写配置，再启动真正的 Godot headless 消费者。它验证初连等待确认、热更新、真实断开连接与自动重连、游戏拒绝并保留有效值、服务类型校验、版本冲突、历史恢复、租户隔离和离线移除。令牌仅留在进程内存和子进程环境；不会使用生产会话。测试在样例目录下创建临时工程和设置，结束关闭进程并删除临时数据库、项目、日志和设置。不会打开编辑器或操作桌面。

客户端本地语义测试为 `tests/unit.gd`；联调消费者为 `tests/live.gd`。正常入口 `main.tscn` 使用同一客户端，展示当前状态、伤害和应用版本。测试通过不意味着已部署服务或安装到用户游戏。
