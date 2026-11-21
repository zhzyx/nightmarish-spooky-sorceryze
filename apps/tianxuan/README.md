# 天璇 Web Shell

天璇产品壳的 Next.js（App Router）前端骨架与无构建视觉样张。

## 页面

- `/` 工作台：AI 指挥台、近期文档、工单、仓库与动态
- `/docs` 文档空间与页面树
- `/docs/[id]` Markdown 编辑器与实时预览
- `/issues` 工单看板与列表
- `/repos` 多宝仓库浏览
- `/requirements` 偃师需求池
- `/settings` 工作区与模型设置
- `/search` 全局搜索

## 本地运行

```sh
pnpm install
pnpm dev
```

生产构建：

```sh
pnpm build
pnpm start
```

### 容器运行包

Web 容器从本目录构建，由仓库内 `deploy/Dockerfile.web` 启用 Next.js standalone。构建输入由 `deploy/Dockerfile.web.dockerignore` 限定。最终镜像使用 Node 自带的 `node` 用户运行 `node server.js`，包含追踪到的生产依赖、`.next/static` 和存在时的 `public`。

监听仍由 `HOSTNAME` 和 `PORT` 控制，默认 `0.0.0.0:3000`。`NEXT_PUBLIC_TIANXUAN_API_BASE` 和 `NEXT_PUBLIC_TIANXUAN_ACTOR` 保持原构建参数。Next 的 `TIANXUAN_API_ORIGIN` 重写在构建时确定，服务端读取的 `TIANXUAN_INTERNAL_API_BASE` 仍可在运行时配置。同源 `/api/` 与实时文档 WebSocket 仍经现有 Nginx 转发。

部署验收应加载绑定源码修订的 OCI 制品，冷启动检查登录、静态资源及动态页面，并验证 WebSocket。回退使用原已验证的 Web 镜像 ID，复用同一代理、API 和数据卷。构建日志不包含目标卷的 blob 去重或快照占用，容量以制品和目标卷回读为准。

## 静态预览

直接双击 `preview/index.html`，或将文件拖入浏览器。样张不依赖构建、网络、外部字体或图片。

## 说明

静态样张使用本地演示数据。Web Shell 按部署能力读取实际服务。


### 工作台对话与仓库

首页使用当前个人 Key 会话读取 `GET /api/v1/issues`。待办与进行中列表均展示实际工单状态。展开工单可查看编号、优先级和关联需求。

首页通过同源 `GET/POST /api/v1/workspace/conversations` 读取和保存当前用户的会话。管理员及编辑角色可以发送消息。服务先记录用户输入，再调用现有模型网关，沿用原预算与用量账本。刷新可恢复历史。模型调用失败会保留原文并标明回复状态。现有 `POST /api/v1/workspace/chat` 仍供调用方提交独立消息上下文。

用户可从对话生成草稿，也可手动填写方向、策划和详细设计。每个阶段需要确认当前版本。修订上游阶段后，下游阶段须重新确认。保存需求会生成可从文档空间读取的需求，包含已确认的版本与验收标准。

在 Godot 业务侧栏打开已有咨询，选择「从咨询形成方向草稿」。可以先手写，再从同一轮问答补充内容，编辑满意后保存修订。Web 的方向、策划和详细设计共用此建议接口。调用方在 `draft_body` 中传入编辑框当前正文；省略该字段时服务读取当前阶段已保存的修订。建议返回完整的可编辑草稿，保留原文并过滤模型原样回显的段落。生成建议本身不写入修订。发布后，从该会话可打开绑定的需求文档及版本。

在 Godot 的「设计文档」中打开一个修订，选中段落后可输入修改要求并预览 AI 建议。建议接口按文档版本和段号读取原段，只把原段和要求发给工作区模型。接受时使用候选正文和原版本保存；相同内容在别处重复出现也只替换所选段，段外空白与换行保持原样。文档已有新版本时，须以新版本重新生成建议。

文曲编辑或恢复会创建新的文档版本。回到该对话后，展开需求版本审阅，检查当前文档并确认该版本，方可再次启动。每次确认保留文曲版本及先前确认的来源，历史执行编号仍可回看。

保存需求后，工作台从 `GET /api/v1/native/entry/capabilities` 读取已准入的执行范围和可用模型配置。默认按任务能力自动选模。用户显式选定范围并启动后，工作台接口复用原生执行账本，按已确认的需求版本写入执行意向，同一事务保存返回的 entry。首页打开该会话时按 entry 自动回读原生状态，离开页面即停止回读。`/api/v1/workspace/runs` 展示当前用户的执行记录和可见工单。

API 服务侧通过 `TIANXUAN_CHAT_MODEL`、`TIANXUAN_CHAT_BASE_URL` 与
`TIANXUAN_CHAT_MODEL_KEY` 注入固定的模型画像。凭据应来自 API 服务的私有环境配置。
撤下任一配置可停用工作台模型，已产生的计量记录仍保存在网关账本。

外观默认为系统设置，用户可在顶栏切换浅色或深色。Windows Godot 使用既有 WebView 同源导航，紧凑窗口采用折叠菜单与单列工单布局。

仓库页根据 `GET /api/v1/capabilities` 显示已启用的能力。原生模块目录从 `/api/v1/workspace/modules` 分页读取可见模块及 head，可打开该修订的对象列表。有 Git 能力的部署提供原有 Git 仓库浏览。

这些接口随现有 FastAPI 和 Web Shell 构建，由现有同源代理接入。会话表复用配置中的天璇数据库。回退时部署上一组 API 与 Web 版本并保留数据库。恢复本版本后可重新读取已保存的会话、需求和执行编号。
