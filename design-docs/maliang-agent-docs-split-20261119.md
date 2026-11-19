# 拆分马良 Agent 图像 Mesh 与骨骼流程文档

<!-- gonggong-request:maliang-agent-docs-split-20261119 -->

日期：2026-11-19（Asia/Shanghai）。路径基准：仓库根。

## 目标与授权

用户要求将马良模块拆分为“生成图、mesh流程”和“生成骨骼流程”，由马良 `README.md` 引用两个子模块，并确认能从根 `AGENTS.md` 正确路由。随后用户明确要求“提交推动到main”，授权本次提交、推送及主线交付。

## 范围

- 根 `AGENTS.md` 的马良路由补充骨骼生成，仍指向 `Markdown/maliang/README.md`。
- 马良 `README.md` 只保留子模块路由和共同约定，不复制具体规则正文。
- 将原有图像／Mesh 生成、视觉 review、增量修复和运行包验收规则完整迁移到 `生成图、mesh流程.md`，保留已有动态 `review_plan` 等在途修改。
- 新增 `生成骨骼流程.md`，整理标准人物、自由 Mesh、SkinTokens 路线及头脸门禁、拟合、蒙皮、ROM／动画验证和发布重载边界。
- 本工单只修改文档、需求记录和交付证据，不改变生成或绑骨实现。

## 验收

- Agent 能从根 `AGENTS.md` 经马良 `README.md` 到达两个唯一正文，完整“图像／Mesh → 骨骼角色”任务可按顺序加载两份细则。
- 原图像／Mesh 规则无丢失，骨骼规则与现有实现设计及 SkinTokens 管线说明一致。
- `git diff --check` 通过，新增及修改文档的相对链接全部有效。
- 通过正式工单门禁和适用的 PR 检查，回读 PR 与远端 `main`，确认精确候选已合入；未通过的检查如实保留。

## 验证记录

- 本地 `git diff --check` 已通过。
- 马良父级及两个子模块的 Markdown 相对链接检查已全部通过。
- 正式门禁、PR 检查和远端 `main` 回读在交付阶段执行并记录实际结果。
