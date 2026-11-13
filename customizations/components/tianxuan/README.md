# 天璇（Tianxuan）

共工框架下的 AI-native 在线管理模块：**文曲**（文档）、**司南**（工单扩展）、**多宝**（代码仓库）。

- 需求 Issue：[#1085](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1085)
- 设计基线：[design-docs/tianxuan-platform-20261114.md](../../../design-docs/tianxuan-platform-20261114.md)
- 素材清单：[design-docs/tianxuan-assets-20261114.md](../../../design-docs/tianxuan-assets-20261114.md)
- 实现状态：已合入 main；产品 Agent/Skill 仍为候选，等待授权批准，`runtime_connected: false`

## 结构

| 路径 | 职责 |
| --- | --- |
| `server/` | 领域核心（SQLite）+ FastAPI 适配层 + 演示与启动入口 |
| `wenqu/` | 文曲：Markdown 规范化、AI 索引、归类、检索、离线三方合并 |
| `duobao/` | 多宝：Git CLI 适配、Gitea/Forgejo HTTP 客户端 |
| `agents/` | 文曲、多宝、司南·工单 Agent/Skill 候选（未准入） |

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

## 环境变量

| 变量 | 用途 |
| --- | --- |
| `TIANXUAN_DB` | SQLite 文件路径，默认 `tianxuan.db` |
| `TIANXUAN_REPO_ROOT` | 需求落库 Git 仓库根（`design/{request_id}.md`） |
| `TIANXUAN_GITEA_URL` / `TIANXUAN_GITEA_TOKEN` | Gitea/Forgejo 地址与 token |
| `TIANXUAN_GITEA_OWNER` | 默认仓库 owner（可选） |
| `NEXT_PUBLIC_TIANXUAN_API_BASE` | Web 访问的 API 地址，默认 `http://127.0.0.1:8000` |
| `TIANXUAN_ACTOR` | Web 服务端渲染使用的 actor（用户 ID） |
| `NEXT_PUBLIC_TIANXUAN_ACTOR` | Web 浏览器端保存实时文档使用的 actor |

## 当前能力

- 身份：注册、登录、Bearer 会话（哈希存储、24h 过期、吊销）、租户角色（admin/editor/viewer）
- 文曲：Markdown CRUD、版本与统一 diff、评论、链接/反向链接、检索、导出、AI 视图、自动归类、AI 结构化补丁
- 协作：WebSocket 实时房间（快照/presence/更新广播）、离线草稿三方合并、Web 端本地草稿与在线同步
- 偃师/司南：需求文档、工单树、状态机、看板、进度同步、需求落库 Git Markdown
- 多宝：本地 Git 提交、Gitea 状态/列表/创建/读取
- AI：BYOK 模型网关（用量与预算）；AI 工具入口
- Web：文档列表/详情/编辑、仓库列表、API 连通状态

## 测试

```sh
python -m pytest customizations/components/tianxuan
```

当前 main 基线：**188 passed + 25 subtests**（以实际运行结果为准）。

## 边界

- 不替代司南的协调与派发责任；工单派发仍走现有司南能力。
- 不重写 Git；多宝复用开源 Git 服务并做 AI 编排与并发合入优化。
- 新增 Agent/Skill（文曲、多宝、司南工单扩展）必须先经 `skills/gonggong-check` 审查并取得精确候选准入。
- 文档以 Markdown 为唯一权威，AI 阅读优先；人类视图是第二等公民。
- 验收沿用现有 Agent（司南协调、偃师设计、夸父质量、谛听证据）。
- 当前认证仍是会话 token + 临时 actor 语义；文档级 ACL 尚未实现。
