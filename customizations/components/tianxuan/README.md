# 天璇（Tianxuan）

共工框架下的 AI-native 在线管理模块：**文曲**（文档）、**司南**（工单扩展）、**多宝**（代码仓库）。

- 需求 Issue：[#1085](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1085)
- 设计基线：[design-docs/tianxuan-platform-20261114.md](../../../design-docs/tianxuan-platform-20261114.md)
- 素材清单：[design-docs/tianxuan-assets-20261114.md](../../../design-docs/tianxuan-assets-20261114.md)
- 实现状态：已合入 main；产品 Agent/Skill 仍为候选，等待授权批准，`runtime_connected: false`

## 结构

| 路径 | 职责 |
| --- | --- |
| `server/` | 领域核心（SQLite）+ FastAPI 适配层 + CLI + 演示与启动入口 |
| `wenqu/` | 文曲：Markdown 规范化、AI 索引、归类、检索、离线三方合并 |
| `duobao/` | 多宝：Git CLI 适配、合入队列、Gitea/Forgejo HTTP 客户端 |
| `agents/` | 文曲、多宝、司南·工单 Agent/Skill 候选（未准入） |
| `apps/tianxuan/` | Next.js Web：文档、工单看板、仓库、设置 |
| `deploy/` | 自托管 Dockerfile、Compose、nginx 与部署说明 |

## 快速开始

### 后端

```sh
cd customizations/components/tianxuan/server
python -m pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

SQLite 默认使用 `tianxuan.db`，可用 `TIANXUAN_DB` 指定路径。

### 端到端演示

```sh
cd customizations/components/tianxuan/server
python demo.py
```

覆盖：注册 → 会话 → 文档 → 结构化补丁 → 评论 → 链接 → 版本差异 → 需求 → 工单 → 看板 → 需求导出。

### Web

```sh
cd apps/tianxuan
npm install
NEXT_PUBLIC_TIANXUAN_API_BASE=http://127.0.0.1:8000 \
TIANXUAN_ACTOR=<user_id> \
NEXT_PUBLIC_TIANXUAN_ACTOR=<user_id> \
npm run dev
```

`TIANXUAN_ACTOR` 用于服务端读取真实文档/仓库；`NEXT_PUBLIC_TIANXUAN_ACTOR` 用于浏览器端保存实时文档。两者都应填写已注册用户的 ID。

### CLI（AI / 脚本）

```sh
cd customizations/components/tianxuan/server
python tianxuan_cli.py --api http://127.0.0.1:8000 docs list
python tianxuan_cli.py login --email owner@example.com --password secret-pass
python tianxuan_cli.py --token <token> docs create --title "CLI 文档" --body "# 标题\n"
```

支持 `docs list/get/create/patch/merge`、`issues list`、`board`、`requirements create/export`；输出 JSON，错误非零退出。

### Docker Compose

```sh
cd deploy
cp .env.example .env
docker compose --env-file .env up -d --build
```

详见 [`deploy/README.md`](../../../deploy/README.md)。

### 天枢互通

引擎内的天枢工作台通过 `server/tianshu_bridge.py` 读写天璇：

```sh
cd customizations/components/tianxuan/server
python tianshu_bridge.py --api http://127.0.0.1:8000 --actor <user_id> \
  context --external-id https://github.com/owner/repo/issues/123
python tianshu_bridge.py --api http://127.0.0.1:8000 --actor <user_id> \
  publish --external-id https://github.com/owner/repo/issues/123 \
  --request-id tianshu-123 --title "需求" --outcome "目标" --scope "范围" --acceptance "验收" \
  --ticket "任务甲" --ticket "任务乙"
```

- `context`：读取该外部工单在天璇内的需求/文档/工单
- `publish`：创建天璇需求与工单树，并写入外部绑定
- `link`：把外部工单绑定到已有文档或工单
- 输出 `{"ok": true, "data": ...}`；`--result <path>` 可直接写天枢宿主回执文件

## 环境变量

| 变量 | 用途 |
| --- | --- |
| `TIANXUAN_DB` | SQLite 文件路径，默认 `tianxuan.db` |
| `TIANXUAN_GATEWAY_DB` | 模型网关用量/预算 SQLite，默认 `:memory:`（重启清空） |
| `TIANXUAN_REPO_ROOT` | 需求落库 Git 仓库根（`design/{request_id}.md`） |
| `TIANXUAN_GITEA_URL` / `TIANXUAN_GITEA_TOKEN` | Gitea/Forgejo 地址与 token |
| `TIANXUAN_GITEA_OWNER` | 默认仓库 owner（可选） |
| `NEXT_PUBLIC_TIANXUAN_API_BASE` | Web 访问的 API 地址，默认 `http://127.0.0.1:8000` |
| `TIANXUAN_ACTOR` | Web 服务端渲染使用的 actor（用户 ID） |
| `NEXT_PUBLIC_TIANXUAN_ACTOR` | Web 浏览器端保存实时文档使用的 actor |

## 当前能力

- 身份：注册、登录、Bearer 会话（哈希存储、24h 过期、吊销）、租户角色（admin/editor/viewer）、单次邀请
- 文曲：Markdown CRUD、版本与统一 diff、评论、链接/反向链接、检索、导出、AI 视图、自动归类、AI 结构化补丁
- 权限：文档 `tenant/private` 可见性、按用户 read/write 共享；列表与所有读路径按 ACL 过滤
- 协作：WebSocket 实时房间（快照/presence/更新广播）、离线草稿三方合并、Web 端本地草稿与在线同步
- 偃师/司南：需求文档、工单树、状态机、工单评论、看板、进度同步、需求落库 Git Markdown
- 多宝：本地 Git 提交；持久化合入队列（预检/检验/串行合入/冲突隔离/证据）；Gitea 状态/列表/创建/读取（支持真实 Gitea 实例）
- AI：BYOK 模型网关（用量与预算）；AI 工具入口；结构化补丁
- Web：文档列表/详情/编辑/共享、实时文档、实时工单看板、实时仓库、设置页系统状态、API 连通状态
- 交付：`deploy/` 自托管 Compose；CLI；端到端演示脚本

## 测试

```sh
python -m pytest customizations/components/tianxuan
```

当前 server 基线：**109 passed**；全模块以实际运行结果为准。

## 边界

- 不替代司南的协调与派发责任；工单派发仍走现有司南能力。
- 不重写 Git；多宝复用开源 Git 服务并做 AI 编排与并发合入优化。
- 新增 Agent/Skill（文曲、多宝、司南工单扩展）必须先经 `skills/gonggong-check` 审查并取得精确候选准入。
- 文档以 Markdown 为唯一权威，AI 阅读优先；人类视图是第二等公民。
- 验收沿用现有 Agent（司南协调、偃师设计、夸父质量、谛听证据）。
- 认证仍是会话 token + 临时 actor 语义；角色为租户级，文档 ACL 已实现，但字段级权限与共享过期尚未实现。
- 产品 Agent/Skill 仍是候选，未经授权批准人签署不得视为已准入。
