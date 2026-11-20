# B02　天璇与偃师的工单、设计、会话和人工判断接口

基线为主线提交 `b60ae96914cd25b0856f4be09b6b0b6a710cc717`。天璇 FastAPI 声明版本为 `0.1.0`，HTTP 命名空间为 `/api/v1`，天璇 Web 包为 `@gonggong/tianxuan-web@0.1.0`。偃师框架定义为 `yanshi@0.4.2`，范围是单功能文档设计，运行需宿主装载。Web 分阶段起草调用模型网关；真正以 `role=yanshi` 派发规划的是原生需求执行服务，须有获准安装、当前需求写权限和所选范围。两条链分别核证。[方案一与 B02 验收](gonggong-ai-workbench-plan1.md#b02) · [工单 #1870](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1870) · [API 声明][api] · [Web 版本](../apps/tianxuan/package.json) · [偃师定义](../framework/agents/yanshi/agent.json) · [规划器][planner]

## 身份、版本与访问范围

| 对象 | 服务实际绑定与约束 | 产品调用点 |
| --- | --- | --- |
| 天璇账号 | `POST /api/v1/auth/session` 用账号换会话；Bearer 取实际用户，退出撤销，过期失效。accounts 模式可通过 Secure、HttpOnly 的会话 Cookie 访问，同源浏览器请求携带 Origin 时响应省略 token。`X-Actor` 仅兼容开关开启时可用。accounts 模式非内部租户的公开工具限于文档。 | [认证与工具白名单][api]、[访问中间件](../customizations/components/tianxuan/server/access_control.py)、[认证用例][auth]。 |
| 工单及计划 | `tenant_id + number` 定位租户内编号，`id` 用于路由。读写重新核对祖先工单所关联需求的 ACL，写入要求相应角色。工单创建有 `created_by`。计划与工时用工作事件 `version`，流程用独立 `flow.version`；写入传各自的 `expected_version` 和稳定 `call_id`。历史工单初始工作版本为 0。 | [工单域][core]、[工作事件][work]、[流程][flow]、[撤权及重放用例][acl]。 |
| 文档与协作 | `doc_id + version` 标识持久正文；版本保留作者及时间。文档可见性、共享、编辑角色、字段策略按动作核对。保存、局部替换和恢复以当前正文版本为基线，版本冲突为 409。 | [文档 HTTP 与房间][api]、[工具、撤权及恢复用例][doctest]、[Web 编辑器][editor]。 |
| 工作台会话与设计 | 私有会话按 `tenant + actor + UUID` 读取，已核验身份或个人访问密钥，viewer 不能写。消息有独立 UUID；会话有递增 `version`。设计阶段共享会话内递增 `revision`，发布后另有 `requirement_id + requirement_version`。已确认的阶段、文档和产物各有自己的版本。 | [工作台身份](../customizations/components/tianxuan/server/gateway.py)、[会话服务][conv]、[Web 对话][chat]、[双用户和过期版本用例][ct]。 |
| 业务模块与历史项目 | 工作台模块目录列已安装或可读的原生模块。迁移服务的 `project` 选择历史目录或新单入口；需求执行的 `requirement-…` 命名空间以来源需求约束读权。方案一的业务模块稳定 ID、工单归属和私人最近位置分别由 C01、C02、C04 接续。 | [模块目录](../customizations/components/tianxuan/server/workspace_inventory.py)、[迁移入口][mig]、[需求来源 ACL][core]。 |
| Godot 现有接入 | 天枢工单详情的“天璇”按钮以当前外部 Issue URL 查绑定。桥支持显式 Bearer 或经配置的外部身份解析；兼容 actor 的适用条件同上。弹窗区分读取、发布需求及同步状态。AI Chat 另有按 conversation/snapshot 关联的偃师需求引导。 | [Godot 弹窗与桥调用][godot]、[桥协议][bridge]、[按钮用例](../editor/docks/daqian/test_tianxuan_workbench.gd)、[AI Chat 需求引导](../editor/docks/ai_chat_gonggong.cpp)。 |

下表的路由均相对 `/api/v1`。`C` 表示 `/workspace/conversations/{key}`，`W` 表示 `/issues/{issue_id}/work`。列出的 Web、桥和服务分别代表已定位的调用点。每行最后一栏给出方案一原生工作台要补的操作或验收，任务 ID 可在[原需求清单](gonggong-ai-workbench-plan1.md)定位。

## 工单

| 任务 | 可复用契约与可回读用例 | 产品接入与具名缺口 |
| --- | --- | --- |
| I01 建单 | `POST /tools` 的 `issue.create` 接收稳定 call_id，返回 id、租户内 number，可从 `GET /issues` 回读。迁移选天璇时 `POST /migration/tasks` 按租户、actor、call_id 重放。见[幂等用例][idem]、[迁移用例][migration-tests]。 | Godot 现有发布按外部需求建树。缺新建时持久保存业务模块 ID 并按编号打开的统一原生入口。 |
| I02 详情 | `GET /issues` 返回可见工单行；`GET W`、`GET W/flow` 分别读计划事件、状态和流程版本。见[工作用例][wt]、[祖先 ACL][acl]。 | Web 工单页用 [IssueWork][wi]。缺负责人、工单正文可寻址版本及按 ID 回读整份详情的原生视图；工作版本不能代表正文版本。 |
| I03 父子 | `issue.create(parent_id)` 或 `POST /requirements/{doc_id}/tickets` 在创建时建父子树，校验祖先读写权，重复拆单可回读相同 ID。[建树用例][scope]、[域实现][core]。 | 天枢可发布树。缺既有工单重新挂接、解除及拒绝父子循环的编辑契约。 |
| I04 依赖 | `POST W/flow/dependencies` 写依赖集，`GET W/flow` 返回 accepted；环路、越权、过期流程版本被拒。普通前置以 done 为准，原生托管前置另需非空 acceptance。[依赖并发与托管验收用例][ft]。 | Web [IssueFlow][fi] 可读写。缺原生阻塞原因及普通单具备验收证据才放行的衔接。 |
| I05 评论 | `GET/POST /issues/{id}/comments` 以当前 actor 写 body，返回评论 ID、作者、时间；viewer 可读，跨租户不可读。[评论顺序及权限用例][comments]。 | 缺工单回复的父评论字段、引用锚点与原生重开定位。文档评论另有 parent_id。 |
| I06 负责人、状态 | `PATCH /issues/{id}` 接收 to_status，`POST W/flow/advance` 带流程版本；规则及撤权覆盖在[流程用例][ft]、[ACL 用例][acl]。 | 天枢桥能同步状态，Web 有流程面板。缺负责人字段、受控改派和原生双视图回读；created_by 仅记录创建者。 |
| I07 迭代与里程碑 | `POST W/plan` 写 iteration、milestone；`GET W` 与 `GET /work/roadmap` 共用同一工单事件投影。[路线图与明细用例][wt]。 | Web [工单计划][wi]。缺原生移单后两个计划视图按同一归属统计的验证。 |
| I08 模块路线图 | `GET /work/roadmap` 按 roadmap、milestone、iteration 排序，只返回可见单。返回 ID、标题、状态、进度、计划和工时，父 ID 可另从工单列表取。[投影][work]、[权限用例][wt]。 | 有 [Web 路线图](../apps/tianxuan/app/issues/roadmap/page.tsx)。缺业务模块关联、父子展开与原生跳转。 |
| I09 自定义字段与阶段 | `POST W/plan` 保存 custom_fields 对象，`POST W/flow/configure` 按工单定义阶段、进度和边。计划浅层更新时传入的 custom_fields 会替换整组。[工作][work]、[阶段配置测试][ft]。 | Web JSON 表单与流程面板可用。缺项目字段定义、未知字段保留策略及动态原生表单。 |
| I10 工时 | `POST W/plan` 保存 estimated_minutes；`POST W/log` 写正整数分钟、备注和 actor。相同键重放与并发防重复见[工时用例][wt]。 | Web [IssueWork][wi] 已提交。缺原生连续登记两次并重试后的累计回读。 |
| I11 检索 | `GET /issues?status=…&requirement_id=…` 从 ACL 过滤后的列表取结果。`GET /search` 搜文档。[列表与查询实现][api]。 | [Web 看板](../apps/tianxuan/app/issues/page.tsx)有实时列表及样例分支。缺业务模块、负责人、关键字组合筛选及空结果复位。 |
| I12 历史原件 | `GET /migration/history/search` 按 project、kind、query 找来源，再用 `GET /migration/history/detail` 或 `/body` 加 source_id 回读。可选 revision 固定该租户的 64 位发布目录摘要，与源 Git 提交区分。历史实录中原件 `github:zhzyx/nightmarish-spooky-sorceryze/issue/1553` 回读 513 字符、3 条反向评论，源提交 `ac8d1376d0a03678b625cbe4bd9b09ea18120475`，跨租户 404，活动单前后均 0。[原实录][hist]、[传输用例][histt]。 | [Web 历史浏览](../apps/tianxuan/app/migration/HistoryBrowser.tsx)有入口。缺原生打开及原件失效时保留来源和 ID 的反馈。 |
| I13 旧会话与在途单 | `GET /external-context?system=…&external_id=…` 是纯读。另行 `POST /requirements/from-external` 才发布；天枢按原 Issue URL 打开已有绑定。[桥][bridge]、[往返及跨租户用例][ext]。 | Godot 有[工单弹窗][godot]。缺旧会话到具有访问权的当前工单定位，按项目、用户重开不执行不复制的实测。 |
| I14 产物与版本 | `GET W` 返回资产事件及 module、revision、path、digest；原生对象路由按修订读字节。`GET W/approved-asset` 只消费当前精确批准的 concept/model。[消费与失效测试][asset]。 | [Godot 导入工具](../customizations/components/tianxuan/duobao/native_godot_import.py)能取 `GET W/godot-inputs` 的当前批准输入包。Web [AssetPreview](../apps/tianxuan/components/AssetPreview.tsx)按精确路径取对象。缺原生在历史修订间选择及对普通附件失效的提示。 |
| I15 关闭、重开 | `PATCH /issues/{id}` 或 `POST W/flow/{advance,judge}`（两条操作）检查允许的边；人工阶段要求 judge。默认 done、cancelled 无出边，自定义配置也禁止终态出边。[状态表][core]、[流程用例][ft]。 | Web 可推进。缺普通单证据校验、重开操作和保留验收历史的原生入口。 |
| I16 聊天办理 | `POST /tools` 暴露 issue.create、issue.transition、issue.list 及允许的 flow 操作；`POST C/turns` 走咨询。work.plan 等内部派发名未进入该公开白名单。[工具入口][api]、[会话测试][ct]、[流程测试][ft]。 | 缺将一次聊天授权限定到当前工单、具体变更和版本，并从 Godot 读回结果的桥。 |
| I17 分类与标签 | `issue.create` 或 tickets 支持 type、priority；当前工单表和状态 PATCH 未提供活动标签集合及类型编辑。[工单结构][core]、[请求字段](../customizations/components/tianxuan/server/schemas.py)。 | 缺按项目维护标签、变更类型并以标签查回原单；无法用文档 tags 代入。 |
| I18 文件附件 | `POST W/submit_asset` 只绑定已存在的 concept/model 修订；`GET /migration/history/attachment` 读取已归档附件（测试按字节回读）。[工作用例][wt]、[归档附件用例][histt]。 | 缺一般文件上传、工单与附件版本绑定、摘要去重和原生选择/下载。 |
| I19 Issue 差额 | 以 I01–I18 为逐项基线，将 [HTTP 白名单][api]、[工作路由][wa]、[历史路由](../customizations/components/tianxuan/server/migration_history_api.py)与实际客户调用分开核对。 | 交给 I19 的复查项是每行末栏（尤其改挂、改派、标签、附件、重开）；届时按原 Issue 使用面补充异常及实测，保持缺口开放。 |

## 设计文档与会话

| 任务 | 可复用契约与可回读用例 | 产品接入与具名缺口 |
| --- | --- | --- |
| D01 默认咨询 | `POST /workspace/conversations` 创建私有会话，`POST C/turns` 按 turn ID 和 expected_version 问答，只走模型回复。执行是独立的 `POST C/execution`，校验已确认需求版本及已选安装范围。[会话用例][ct]。 | [Web 对话][chat]可续问。缺 Godot 同一咨询入口收到“请改代码”时只给建议的实测。 |
| D02 按文档打开 | `GET /docs/{doc_id}` 和 `GET /docs/{doc_id}/versions/{version}` 核对当前访问权，以 ID、版本区分同名文档。[版本列表与读取测试][vt]。 | Web 需求页可打开 doc_id；原生缺能重定位到确切修订中段落的锚点协议。 |
| D03 讨论起草 | `POST C/design/{stage}/suggest` 从最近讨论与已确认前序生成建议；只读。显式 `POST …/drafts` 才写；详设须有标题和验收，`POST C/requirement` 固定三阶段关联。[阶段服务][conv]、[会话用例][ct]。 | [Web 设计面板][design]可先看后存。缺 Godot 逐段映射问答、保护已写段落的合并。 |
| D04 手工正文 | `POST /docs`、`PATCH /docs/{doc_id}` 支持先写文档；`POST /requirements` 可直接建需求。文档版本记录 author，读版本回放。会话内阶段草稿则要求先有 turn。[文档端点][api]、[版本测试][vt]。 | [Web 创建文档](../apps/tianxuan/components/CreateDoc.tsx)与编辑器已接。缺 Godot 纯手工保存、关闭、重开定位作者和段落。 |
| D05 局部修改 | `POST /docs/{doc_id}/patch` 或 doc.patch 以 expected_version 和唯一 find/replace 应用修改，过期、未找到、匹配多处均拒绝。[局部替换测试][patch]。 | 该写操作会直接生成正文修订。缺接受前的原生候选、指定段落与差异预览。 |
| D06 版本恢复 | `GET /docs/{id}/diff?from_version=…&to_version=…`，`POST /docs/{id}/versions/{v}/restore` 带 expected_version，恢复追加历史并拒绝过期写。[版本][vt]、[恢复与重放][doctest]。 | [Web 版本页](../apps/tianxuan/components/DocVersions.tsx)已有。缺原生 A→B→恢复 A 的展示及定位。 |
| D07 双用户 | `WS /ws/docs/{id}` 广播房间状态与更新，`POST /docs/{id}/merge` 以存储的基线版本和正文合并；不同段可并，同段冲突保留供判断。[WebSocket 用例][ws]、[合并测试][merge]。 | [Web 双账号既有实录][collab]。缺 Godot 房间订阅、合并冲突双份正文展示。 |
| D08 离线草稿 | [Web 编辑器][editor]按账号 ID 和 doc_id 缓存草稿及基线；重连调用 merge，旧格式缺基线时可导出恢复。[合并测试][merge]、[离线重连实录][collab]。 | 缺原生本地草稿保存、重开和重连冲突处理。 |
| D09 确认指定修订 | `POST C/design/{stage}/confirm` 需当前会话版本及阶段 revision，保存 confirmed_by、confirmed_at。旧请求可 409，不会多签；改写上游清除后续当前指针。发布后 `GET/POST C/requirement-review` 审阅并重新确认精确正文版本。[会话用例][ct]。 | Web 已能复核。缺原生重复点击后的回读、新正文不继承旧授权的反馈。 |
| D10 设计拆单 | `POST /requirements/{id}/tickets` 幂等建父单与子单，但请求本身无确认版本字段。受控执行链另校验源版本、调用获准偃师，验证任务范围并持久化到同一工单树。[拆单重放][scope]、[规划实现][planner]、[规划器持久化用例][nt]。 | [Web 执行](../apps/tianxuan/components/WorkspaceExecution.tsx)显式选择范围。缺 Godot 将程序、动画两单映射回同一确认修订的样例。 |
| D11 增量或新建 | 新建用 `POST /requirements`（request_id）；追加用 `PATCH /docs/{id}` 或 `POST /docs/{id}/patch`（expected_version）。已发布会话需重新确认新版本。[幂等][scope]、[正文修改][patch]、[重新确认][ct]。 | 缺 Godot 让用户选择已有文档或新建，回读目标、版本及增量。 |
| D12 重开会话与未发草稿 | `GET /workspace/conversations`、`GET C` 回读私有已发轮次，重复 turn ID 不重发。pending 可 `POST C/turns/{turn_id}/stop-waiting`，迟到回答不覆盖；失败保留原文。[未答、重复及迟到测试][ct]。 | Web 输入草稿是组件内状态。缺项目、模块、工单、账号联合归属，以及未发内容和附件引用的持久恢复。 |
| D13 偃师阶段 | `GET C` 的 current 与 revisions 映射 direction、plan、design；保存新上游不删除旧历史，未确认前序不能推进。[阶段实现][conv]、[顺序和旧版拒绝用例][ct]。 | Web [设计面板][design]已显示阶段与版本。缺原生阶段视图、定位及结构化退回意见。 |
| D14 原生业务身份 | `POST /auth/session`、`POST /auth/logout`，桥可 `POST /identity/resolve` 再带 token 访问；该可选缓存按 API、provider、subject 分开。Web 的工作台会话另走 workspace_actor。[身份与撤销][auth]、[桥身份用例][bt]。 | Godot 弹窗已有外部身份路径。缺按项目绑定当前账号、换号清理会话与失效重登的统一客户端及无凭据落入项目的验证。 |

## 创意判断

| 任务 | 可复用契约与可回读用例 | 产品接入与具名缺口 |
| --- | --- | --- |
| H01 发起人默认判断 | `POST W/submit_asset` 固定 kind、module、revision、path、digest，事件记录提交 actor；新版重新 pending。[版本签认测试][wt]。 | 工单有 created_by。缺判断项独立的发起人、当前判断人字段及“代执行不改归属”的约束。 |
| H02 转交 | `GET W` 可回读待审产物和历史意见；写操作集合只有 plan、log、submit_asset、decide。[路由][wa]。 | 缺转交接口、目标用户接收、原页失权、原设计与既有意见的版本化记录。 |
| H03 本人待办 | `GET W` 给单个可见工单的当前资产状态；Web 首页从可见工单按状态列待办。[工作投影][work]、[首页](../apps/tianxuan/components/DashboardWorkspace.tsx)。 | 缺以登录判断人为条件、包含问题及确切修订的跨单待办和原生直达。 |
| H04 候选并排 | `GET W` 中 history 留历次提交，assets 按 kind 投影最新；Web [资产预览](../apps/tianxuan/components/AssetPreview.tsx)按 module/revision/path 读取。[版本绑定用例][wt]。 | 缺把同类多个候选及对应设计并列、各自打开原件、选择操作绑定所点版本。 |
| H05 签认 | `POST W/decide` 接受 approved 或 changes_requested、note、精确资产标识、expected_version、call_id；记录 actor，过期资产被拒。公开 AI 工具未暴露 decide；服务内普通派发也不赋 human 标志。[HTTP 路由][wa]、[美术回归][wt]。 | Web 工单页可签认。接口核工单写权，尚缺仅指定判断人可签、通用候选保留与原生签认；持有人的写凭据不能证明由人实际操作。 |
| H06 局部阻塞 | `POST W/flow/dependencies` 给指定工单建边，`POST W/flow/judge` 同版本同 call_id 重试可回原结果；其他工单各自读依赖。托管前置缺验收仍阻塞。[流程与重复签认用例][ft]。 | 缺“某个创意修订获签→只唤醒指定后继一次”的事件关联，以及动画等待期间程序继续的组合验证。 |

## 交接与复验

B05 可用两个用户、两个同名模块和工单测试身份及隔离，C01 接稳定业务模块键，D14 接 Godot 业务会话，I12 接已发布的历史原单，B07 汇总本表所列的可复用接口和缺口。验收范围是此能力矩阵。Web 历史回执注明其基线，本次复跑在隔离测试库内完成；原生产品交互仍由各对应任务实测。

在仓库的 `customizations/components/tianxuan/server` 目录运行以下命令。复现时先运行 `py -3.14 -m venv "$env:TEMP/gonggong-plan1-b02-1870-20261121"`，再运行 `& "$env:TEMP/gonggong-plan1-b02-1870-20261121/Scripts/python.exe" -m pip install -r requirements.txt`。实测环境为 Python 3.14.3、pytest 9.2.0、FastAPI 0.165.0、Starlette 1.10.0、httpx 0.28.1。

```powershell
& "$env:TEMP/gonggong-plan1-b02-1870-20261121/Scripts/python.exe" -B -X utf8 -m pytest -q -p no:cacheprovider test_api_session.py test_workspace_conversations.py test_work_management.py test_issue_flow.py test_issue_comments.py test_issue_ancestor_acl.py test_api_patch.py test_api_versions.py test_ai_document_tools.py test_ws.py test_api_merge.py test_migration_history_api.py test_approved_asset.py test_tianshu_bridge.py test_scope_idempotency.py test_external_links.py test_api_doc_issues.py
& "$env:TEMP/gonggong-plan1-b02-1870-20261121/Scripts/python.exe" -B -X utf8 -m pytest -q -p no:cacheprovider test_api_auth_mode.py test_migration_api.py test_tool_receipts.py test_native_entry.py -k "auth or migration or receipt or planner_persists_existing_issues or committed_plan_survives_dispatch_gap"
```

第一组 84 passed，耗时 18.54s。第二组 71 passed、15 deselected，耗时 18.73s。两组各有一条 Starlette TestClient 使用 httpx 的弃用提示。测试中的兼容 X-Actor 由 conftest 显式开启；认证专测覆盖默认关闭，工作、判断及会话用例也覆盖已认证路径。两组仅使用隔离回执，未进行生产写入。

[api]: ../customizations/components/tianxuan/server/api.py
[core]: ../customizations/components/tianxuan/server/tianxuan_core.py
[auth]: ../customizations/components/tianxuan/server/test_api_session.py
[acl]: ../customizations/components/tianxuan/server/test_issue_ancestor_acl.py
[wa]: ../customizations/components/tianxuan/server/work_management_api.py
[work]: ../customizations/components/tianxuan/server/work_management.py
[wt]: ../customizations/components/tianxuan/server/test_work_management.py
[flow]: ../customizations/components/tianxuan/server/issue_flow.py
[ft]: ../customizations/components/tianxuan/server/test_issue_flow.py
[wi]: ../apps/tianxuan/components/IssueWork.tsx
[fi]: ../apps/tianxuan/components/IssueFlow.tsx
[idem]: ../customizations/components/tianxuan/server/test_tool_receipts.py
[scope]: ../customizations/components/tianxuan/server/test_scope_idempotency.py
[comments]: ../customizations/components/tianxuan/server/test_issue_comments.py
[mig]: ../customizations/components/tianxuan/server/migration_api.py
[migration-tests]: ../customizations/components/tianxuan/server/test_migration_api.py
[asset]: ../customizations/components/tianxuan/server/test_approved_asset.py
[hist]: ../data-collection/tianxuan-history-lookup-1553.json
[histt]: ../customizations/components/tianxuan/server/test_migration_history_api.py
[bridge]: ../customizations/components/tianxuan/server/tianshu_bridge.py
[godot]: ../editor/docks/daqian/workspace.gd
[bt]: ../customizations/components/tianxuan/server/test_tianshu_bridge.py
[ext]: ../customizations/components/tianxuan/server/test_external_links.py
[editor]: ../apps/tianxuan/components/DocEditor.tsx
[conv]: ../customizations/components/tianxuan/server/workspace_conversations.py
[ct]: ../customizations/components/tianxuan/server/test_workspace_conversations.py
[chat]: ../apps/tianxuan/components/AICommandBar.tsx
[design]: ../apps/tianxuan/components/WorkspaceDesign.tsx
[vt]: ../customizations/components/tianxuan/server/test_api_versions.py
[doctest]: ../customizations/components/tianxuan/server/test_ai_document_tools.py
[patch]: ../customizations/components/tianxuan/server/test_api_patch.py
[ws]: ../customizations/components/tianxuan/server/test_ws.py
[merge]: ../customizations/components/tianxuan/server/test_api_merge.py
[collab]: ../data-collection/tianxuan-a3-1568/integration.md
[planner]: ../customizations/components/tianxuan/sinan-workorders/native_requirement_plan.py
[nt]: ../customizations/components/tianxuan/server/test_native_entry.py
