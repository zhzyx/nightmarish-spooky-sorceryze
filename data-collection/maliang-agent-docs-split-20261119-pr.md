# 马良 Agent 文档拆分交付说明

工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1619

稳定需求 ID：`maliang-agent-docs-split-20261119`

## 范围

- 根 `AGENTS.md` 将马良图像、网格、骨骼任务路由到马良模块索引。
- 马良 `README.md` 引用图像／Mesh 与骨骼两个子流程，只保留共同约定。
- 原图像／Mesh 生成、视觉 review、增量修复及运行包验收正文迁移到独立细则，保留动态 `review_plan` 等在途修改。
- 新增骨骼生成细则，覆盖标准人物、自由 Mesh、SkinTokens、头脸门禁、蒙皮、ROM／动画验证和发布重载。
- 不包含生成、绑骨或编辑器代码变更。

## 验证

- `git diff --check`：通过。
- 马良父级与两个子模块的 Markdown 相对链接检查：全部有效。
- `issue_gate.py --intake-only`：已回读 Issue #1619，类别 `type:documentation`，状态 `status:in-progress`。
- 已记录谛听 request 源事件，校验和为 `32504383b67ce787431516cc6938cc49238a197b83c77aab5d652ce4c3f5f910`。

## 审查与交付边界

本候选仅包含根导航、`Markdown`／`design-docs` 文档及交付证据，按 `tier0_docs_telemetry` 执行正式门禁、静态检查和 Issue 关联检查；不声称完成任何真实图像、Mesh、骨骼或动画生成验收。其他未暂存的在途代码、资产和测试修改不属于本候选。
