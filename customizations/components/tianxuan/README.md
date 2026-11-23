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
- Tianshu 的 Issue 详情新增「天璇」按钮：读取已绑定需求/文档，未绑定时可一键发布需求与工单树
- 天枢节点状态变为 done 时自动调用 `sync` 回写天璇工单；非当前工单在 board 刷新时也会回写；失败/未绑定保留，按 60 秒间隔最多重试 3 次；新的完成事件会重置重试计数，弹窗显示待重试项并可「立即重试」
- Tianshu 侧通过 `TIANXUAN_API`、`TIANXUAN_ACTOR` 或 `TIANXUAN_TOKEN` 指定天璇连接身份
- 身份适配：`/api/v1/identity/links` 绑定外部身份，`/api/v1/identity/resolve` 按 provider 适配器换取会话；内置 `static`、`tianshu`/`github` 共享密钥、`oidc` JWT 适配器（HS256 用 `TIANXUAN_OIDC_SECRET`；RS256 用 `TIANXUAN_OIDC_JWKS`、`TIANXUAN_OIDC_JWKS_URL`，或 `TIANXUAN_OIDC_DISCOVERY_URL` 自动发现 jwks_uri/issuer；JWKS 5 分钟缓存，未知 kid 时 30 秒节流强制刷新；discovery/JWKS 默认要求 https（localhost 例外，`TIANXUAN_OIDC_ALLOW_INSECURE=1` 可放宽）；可选 `TIANXUAN_OIDC_ISSUER`/`TIANXUAN_OIDC_AUDIENCE`；默认要求 `exp`，`nbf`/`iat` 超前 60s 拒绝，`TIANXUAN_OIDC_ALLOW_NO_EXP=1` 可放宽）

### 共工项目的多宝写入入口（G22）

在已安装的天枢打开共工 Git 工作副本中的 Godot 项目。「多宝分支」「多宝提交」「多宝合入」使用该项目所属仓库，审查和交付沿同一合入请求进行。安装宿主只把共工的原仓标识 `zhzyx/nightmarish-spooky-sorceryze` 映射到 `https://167-172-70-41.sslip.io` 的 `gonggong.git`，匹配 Git 本地配置中的单一 HTTPS 或 SSH origin。普通项目保留原连接方式。测试和本地服务可显式指定 `TIANXUAN_API` 和 `TIANXUAN_GIT_REPO`。项目文件不能填写目的服务地址。

以下命令从可信宿主根运行。第一条在本机读取路由，第二条以当前操作者的天璇身份回读目标分支。两条命令均可指定 Git 工作树下的项目目录。使用启动环境中的会话或身份交换密钥时，在可信启动器显式指定该凭据所属的 `TIANXUAN_API`。自动选择公网入口仅接受按该 origin 和身份绑定的会话缓存，或调用者在本次命令显式提供的令牌；仅有旧启动环境的凭据时会提示绑定服务。

```sh
python customizations/components/tianxuan/server/tianshu_bridge.py --workspace <项目目录> duobao-route
python customizations/components/tianxuan/server/tianshu_bridge.py --workspace <项目目录> branch-tip --branch main
```

桌面交付需配套发布编入编辑器的 `editor/docks/daqian/workspace.gd` 与该版本安装宿主的 `server/tianshu_bridge.py`。Windows 主检出可从同修订成功的 Actions 运行执行 `tools/install_gonggong_editor.ps1 -ActionsRun <运行编号>`，首次安装和已有安装升级复用同一入口。完整工作区 ZIP 的使用者按发布索引校验并解压至新目录，打开自己的共工 Git 工作副本。macOS 完整构建提供 `macos-editor` 产物，裸编辑器使用同修订的宿主树及随附资源。在应用包内发布时，先放置 Mach-O 和两个天枢资源包，再签名、验证和切换现用应用。升级保留上一份可用的宿主和编辑器，回退时成对恢复。覆盖率需由各客户端回读，受控的显式本地配置可独立回退。[Windows 安装](../../../project/godot/README.md) · [完整包分发](../../../distribution/README.md) · [macOS 构建](../../../.github/workflows/macos_builds.yml)

## 环境变量

| 变量 | 用途 |
| --- | --- |
| `TIANXUAN_DB` | SQLite 文件路径，默认 `tianxuan.db` |
| `TIANXUAN_GATEWAY_DB` | 模型网关用量/预算 SQLite，默认 `:memory:`（重启清空） |
| `TIANXUAN_REPO_ROOT` | 需求落库 Git 仓库根（`design/{request_id}.md`） |
| `TIANXUAN_GITEA_URL` / `TIANXUAN_GITEA_TOKEN` | Gitea/Forgejo 地址与 token |
| `TIANXUAN_GITEA_OWNER` | 默认仓库 owner（可选） |
| `TIANXUAN_GITEA_WEBHOOK_SECRET` | Gitea webhook HMAC-SHA256 密钥；未设置时 webhook 返回 503 |
| `TIANXUAN_PROTECTED_BRANCHES` | 受保护分支模式（逗号分隔，支持 `release/*`） |
| `TIANXUAN_REQUIRED_APPROVALS` | 合并所需独立批准数（默认 0） |
| `TIANXUAN_REQUIRED_CHECKS` | 合并前必须 success 的提交检查 context（逗号分隔） |
| `TIANXUAN_IMPORT_ALLOW_LOCAL` | 允许本机路径/`file://` 仓库导入（默认 0） |
| `TIANXUAN_IMPORT_ALLOWED_HOSTS` | 导入来源主机白名单（逗号分隔） |
| `TIANXUAN_ALLOW_ACTOR_HEADER` | 兼容开关：为 `1` 时接受 `X-Actor`；默认 `0`，必须使用 Bearer 会话 |
| `TIANXUAN_TOKEN` | Web 服务端渲染使用的会话 token（可选；未设置时回退 `X-Actor`） |
| `NEXT_PUBLIC_TIANXUAN_API_BASE` | Web 访问的 API 地址，默认 `http://127.0.0.1:8000` |
| `TIANXUAN_ACTOR` | Web 服务端渲染使用的 actor（用户 ID） |
| `NEXT_PUBLIC_TIANXUAN_ACTOR` | Web 浏览器端保存实时文档使用的 actor |

## 当前能力

- 身份：注册、登录、Bearer 会话（哈希存储、24h 过期、吊销）、租户角色（admin/editor/viewer）、单次邀请；Web `/login` 登录页把 token 存入 localStorage 与同站 cookie，API 客户端优先发送 Bearer，`X-Actor` 默认关闭
- Web 身份加载：浏览器有会话 token 时面板无需 `NEXT_PUBLIC_TIANXUAN_ACTOR` 即可加载（`useActor` 在挂载后切换到 token 模式）；服务端渲染在未配置 `TIANXUAN_ACTOR` 时可用 `TIANXUAN_TOKEN` 发起请求
- Gitea 身份映射：写操作要求操作者已绑定 Gitea 身份（`identity_links` provider=`gitea`、subject=Gitea 用户名），服务端用 `Sudo` 头代表该用户；`TIANXUAN_GITEA_TOKEN` 需为具备 sudo 权限的 token，未绑定用户的写入返回 403，读路径回退服务身份
- 文曲：Markdown CRUD、版本与统一 diff、评论、链接/反向链接、检索、导出、AI 视图、自动归类、AI 结构化补丁
- 权限：文档 `tenant/private` 可见性、按用户 read/write 共享；列表与所有读路径按 ACL 过滤
- 协作：WebSocket 实时房间（快照/presence/更新广播）、离线草稿三方合并、Web 端本地草稿与在线同步
- 偃师/司南：需求文档、工单树、状态机、工单评论、看板、进度同步、需求落库 Git Markdown；文档↔工单双向关联（`doc_issue_links`，列表/关联/解绑，幂等，租户隔离）
- 多宝：本地 Git 提交；持久化合入队列（预检/检验/串行合入/冲突隔离/证据；可选 PR/工单绑定，重试/取消限创建者或 admin，事件回执可接领域事件）；默认启动自动 worker，设 `TIANXUAN_MERGE_WORKER=0` 可关闭；检查在临时 worktree 执行，使用独立 HOME/TEMP 且默认不继承 `TIANXUAN_*`/TOKEN/SECRET 等环境，`TIANXUAN_MERGE_CHECK_ENV` 可白名单；Gitea 仓库/分支/PR/评审/提交状态；保护分支、批准数与必需检查的合并门禁；镜像导入与标签列表
- 仓库绑定与 webhook：`/api/v1/repo-links` 把 `provider/owner/name` 绑定到租户（全局唯一，admin 管理）；`/api/v1/webhooks/gitea` 校验 HMAC 签名后把 push/PR 事件写入对应租户事件流，未绑定仓库与不支持事件返回 202 ignored
- AI：BYOK 模型网关（用量与预算）；AI 工具入口；结构化补丁
- Web：文档列表/详情/编辑/共享、Markdown/HTML/Word/PDF 导出（HTML 为安全 Markdown 渲染；PDF/DOCX 支持 data URI 图片；远程图片需 `TIANXUAN_EXPORT_IMAGE_HOSTS` 白名单）、实时文档、实时工单看板、实时仓库、仓库文件树/分支/标签面板（目录浏览、建删分支、标签查看/建删、子模块只读展示、LFS 指针标识、镜像导入任务与进度、代码搜索/逐行追溯）、PR 评审（批准/要求修改/评论与评审计数）、PR 状态筛选与分页（open/closed/all）、发布列表/创建/编辑（releases）、合入 worker 注册/心跳、中英文切换（外壳、登录、工作台含 AI 指令条、404、API 状态、文档列表/详情、文档编辑器、文档导出/共享（含有效期）/评论/版本历史/身份绑定/天枢来源、工单列表/看板、需求页、搜索页、设置页、仓库页/文件树、本地仓库、PR、合入队列已接入，其余面板文案待迁移）、设置页系统状态、API 连通状态
- 交付：`deploy/` 自托管 Compose（含 TLS/门禁 profile、备份脚本与 Gitea/GitHub Actions 状态回写模板）；CLI；端到端演示脚本；`/api/v1/ready` 就绪探针、`/api/v1/metrics` Prometheus 指标与 `duobao/backup_drill.py` 备份恢复演练

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
- 认证默认使用 Bearer 会话（`/api/v1/auth/session`）；Web 登录页把 token 存入 localStorage 与同站 cookie，`X-Actor` 仅在显式开启时兼容；角色为租户级，文档 ACL 与字段级写入权限（title/body_md/status/visibility 的最低角色，owner/admin 配置）已实现。
- 产品 Agent/Skill 仍是候选，未经授权批准人签署不得视为已准入。
