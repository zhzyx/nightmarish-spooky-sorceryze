# 文曲（文档）

Markdown 为唯一权威，AI 阅读效率优先；人类视图与导出是第二等公民。

## 已实现（领域核心）

- `server/tianxuan_core.py`：文档创建/更新、版本快照、乐观并发、自动归类、`ai_view` 机器视图。
- 需求文档：frontmatter（`request_id`、`kind`、`lang`）+ 目标/范围/验收正文。

## 规划

- 实时协同（Yjs/Hocuspocus）与评论/建议模式。
- 版本 diff、恢复到指定版本。
- 导出 md / pdf / docx / html。
- 离线草稿队列与冲突合并（Web 优先）。
- 语义检索（pgvector）与全文检索。

## 约定

- 稳定标题锚点与 `[[wiki-link]]` 引用。
- 归类先规则、后模型，人工可纠正。
- 不把二进制块塞进 Markdown 正文；附件走对象存储引用。
