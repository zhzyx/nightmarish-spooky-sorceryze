# 同步共工合契 0.2.0 到 Olympus

工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/27
稳定需求 ID：`heqi-olympus-sync-20261103`。上游需求为共工 Issue #25；该单只覆盖 Olympus 分发候选与准入，不修改共工源或 #22 聊天引导。

## 本轮边界

以共工最终 release-ready 的 `CURRENT_FRAMEWORK.json`、完整清单和正式来源校验为输入，在独立 worktree 使用 `Olympus/sync/gonggong_sync.py` 全量重建，不挑选文件。确定性名称映射须覆盖新增合契 Agent 与相关 skill、审查和 reporting 引用；同步后的身份采用 Olympus 命名，源身份和哈希保留在 `source-evidence.json`。`Olympus/extensions/hermes-files/` 逐字节保留，根目录 `olympus-hermes-data/` 不由同步清理。运行时默认不注册真实来源、不启用 Agent。

产物为完整 Olympus 框架差异、候选/独立审查与准入记录、代表行为验证、`data-collection/` 来源及验证证据、`olympus-hermes-data/` 真实文件事件和 Git 交付。目标平台为当前 Windows 本地分发验证；不扩展 Godot 引擎构建、共工宿主部署或其他平台。先跑源完整性、全量 parity、候选/正式准入及相关行为测试，再按实际失败扩大。提交前执行 #27 门禁，提交后执行 Hermes `git-check --require-committed`，远端推送与 PR 分别回读。

## 停止与恢复条件

当前共工来源已报告合契入口指纹漂移、finish 上报与正式校验未通过。本轮准备阶段不消费该漂移源。收到精确冻结清单、正式校验和 finish 实际送达回执后重新核对输入；若候选指纹、准入或独立审查缺失，保留待审候选，不声称 Agent 启用。Issue #25 的上游批准不代替 Olympus 映射后候选的精确准入。

## 冻结源到候选的实际结果

共工随后交付 `heqi-integration-25/frozen-v1` 固定源。原始 200 文件清单见 `data-collection/issue27-frozen-source.json`，逐项摘要吻合；正式源校验通过。同步工具从该框架目录重建 154 个分发文件，源框架文件 182 个，`check` 全量 parity 通过。合契 0.2.1 映射为哈耳摩尼亚 `harmonia`；新增的 Git Issue 可选模块按源全量进入候选，默认不启用。旧精确候选的本地准入原件逐字保存于 `data-collection/issue27-previous-local-admission/`，不套用到新摘要。

分发布局适配修复了源测试在 Olympus 包内定位 `framework/` 的错误；名称转换保护宿主交接目录 `data-collection`，避免把它当成 `data-collect` 组件改写。运行时测试夹具的审查路径按本地准入证据目录适配。这些转换都在同步工具中确定性重建并纳入 parity，不手改生成包。

Windows 本地验证：Git Issue 模块 8 项、Ariadne 12 项、框架 Python 19 项通过；候选完整性、质量归属及 Python/Node 语法通过。框架正式验证明确失败于 `pending_independent_review`，这是未准入状态的预期阻断。共工 0.2.0 的实际本地 Git 冲突验证与 0.2.1 算法未变复核只按其原范围复用，不声称新版本或多账号生产实测。摘要与范围见 `data-collection/issue27-sync-candidate-20261104.json`；真实请求和候选文件事件已写入 `olympus-hermes-data/`。候选需 Olympus 独立审查及精确批准后，才能按正式门禁提交和启用；目前不宣称发布完成。

## 独立审查后的本地定义准入

另一审查实例未参与 Olympus 映射适配，完成四 Agent 精确候选、全量 parity、runtime lock、reporting 与豁免的独立复核，原件为 `Olympus/reviews/local-admission/issue27-independent-review.json` 和 `issue27-review-scenarios.json`。复核是 pass 而非批准。随后依据用户“验证好了之后推送到 Olympus 框架更新”的条件性授权，仅为 `athena`、`themis`、`hermes`、`harmonia` 四个精确摘要签发本地定义许可；决定依据与四份许可同在 `Olympus/reviews/`。正式 `verify_framework.py` 已返回 `approved_file_integrity`，合契准入检查和冻结源 parity 均通过，见 `data-collection/issue27-admission-20261104.json` 及追加 Hermes 事件。原先的 pending 观察记录保留，不改写历史。宿主运行授权、可选 Git Issue 模块启用、远端提交/合入和谛听消费仍分别待证。

## PR 静态检查修复

PR #34 的 CI 指出仓库级离线登记仍固定为旧三 Agent 快照，文档还需要统一格式。已将非豁免 Olympus 文件重新逐字节登记，并让校验器按当前 manifest 校验非空且唯一的 Agent 集合；生成框架与四份准入文件未变。对应来源、修复摘要与本地复验见 `data-collection/issue27-ci-repair-20261104.json` 和追加 Hermes 事件。
