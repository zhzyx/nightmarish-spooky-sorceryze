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
