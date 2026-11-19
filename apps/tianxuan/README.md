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

以上依赖安装与构建不在本次交付范围内执行；当前交付的验证方式见下。

## 静态预览

直接双击 `preview/index.html`，或将文件拖入浏览器。样张不依赖构建、网络、外部字体或图片。

## 说明

当前所有内容均为本地演示数据，不连接后端、模型或 Git 服务，不包含任何凭据。


### 工作台对话与仓库

首页使用当前个人 Key 会话读取 `GET /api/v1/issues`。待办与进行中列表均展示实际工单状态。展开工单可查看编号、优先级和关联需求。

`POST /api/v1/workspace/chat` 通过现有同源代理进入 FastAPI。请求体为
`{"messages":[{"role":"user","content":"…"}]}`，回复包含 `model` 和 `content`。
生产端使用已配置的个人 Key 租户，管理员及编辑角色可以发送消息。对话网关沿用现有预算与用量账本。
API 服务侧通过 `TIANXUAN_CHAT_MODEL`、`TIANXUAN_CHAT_BASE_URL` 与
`TIANXUAN_CHAT_MODEL_KEY` 注入固定的模型画像。凭据应来自 API 服务的私有环境配置。
撤下任一配置可停用工作台模型，已产生的计量记录仍保存在网关账本。
浏览器提交最近十二轮上下文，页面离开后本次对话记录结束。持久会话及对话转需求由整合任务验收。

外观默认为系统设置，用户可在顶栏切换浅色或深色。Windows Godot 使用既有 WebView 同源导航，紧凑窗口采用折叠菜单与单列工单布局。

仓库页根据 `GET /api/v1/capabilities` 显示已启用的能力。原生版本按模块名读取实际 head 与该修订的对象列表。模块目录等待部署侧的原生枚举接口。有 Git 能力的部署继续提供原有 Git 仓库浏览。
