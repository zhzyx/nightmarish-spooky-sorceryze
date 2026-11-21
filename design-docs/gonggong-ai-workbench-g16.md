# G16　存量 PR 交接表

本表接续 G01 冻结快照中的 5 个开放 PR。回读时 5 个仍开放，原作者、目标分支和候选 head 均与快照相同。原作者继续负责原平台收尾，表中审查人取自 GitHub 的审查请求。[冻结清单](../data-collection/gonggong-ai-workbench-g01-inventory.json) · [逐单候选与验收回执](../data-collection/gonggong-ai-workbench-plan1-g16.json)

| 原 PR | 业务单 | 原作者与审查 | 接续动作 |
| --- | --- | --- | --- |
| [#1661](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/1661) | [#1642](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1642) · OPEN | Sail-Li · zhzyx | 由 Sail-Li 在 #1642 接续天璇内容回退和发布历史验收，向已请求的审查人提交原候选或绑定后的修订。 |
| [#1245](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/1245) | [#951](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/951) · OPEN | Sail-Li · zhzyx | 由 Sail-Li 在 #951 核对跨控制器会话的接续验收，并同 #1234 比较独有修改，记录最终采用的精确候选。 |
| [#1234](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/1234) | [#951](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/951) · OPEN | Sail-Li · zhzyx | 由 Sail-Li 确认草稿与 #1245 的共同及独有修改。在原 PR 记录继续审查或被替代的决定及对应链接。 |
| [#1216](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/1216) | [#1168](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1168) · CLOSED | Sail-Li · zhzyx | 由 Sail-Li 核对已完成的 #1168 实际接收修订与本 PR 的 Windows 共享冲突回归，注明是否仍有未交付差异。 |
| [#645](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/645) | [#49](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/49) · CLOSED | kaiyunxue · 待指定 | 由 kaiyunxue 确认已完成的 #49 与本草稿保留的运行时恢复候选是否一致，再指定审查人或签认结转理由。 |

原平台合入时，由迁移负责人以实际 merge OID 进行 G17 增量同步，将来源 PR、精确修订和多宝接收回执交给 G23 核销。原平台关闭而未合入时，归档关闭理由、时间、最后 head 和原单链接，若由其他 PR 替代，同时归档其链接。切换时仍开放的记录保留 GitHub 审查入口，由 G24 逐条跟踪。[G17](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1741) · [G23](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1720) · [G24](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1725)

迁移负责人需确认两类例外。#1234 与 #1245 关联同一工单且 head 不同，要分别保留其原始内容并由原作者确认采用范围。#1216 与 #645 的业务工单已经关闭，仍需原发布者核对尚未合入的 PR 候选；#645 还需由原作者确定审查去向。确认前保留现有状态。[G16 原工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1782)
