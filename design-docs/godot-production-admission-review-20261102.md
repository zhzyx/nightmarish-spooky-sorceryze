# 生产聊天准入：独立审查与待批准对象

请求：`godot-host-portability-20261102`。此文件记录实际审查，**不是批准通行证**。

## 已完成的源增量独立审查

评价者：`/root/review_upstream`，独立子 Agent。范围为共工当前 0.9.0 源中两项 Agent 的路径迁移增量及本地定义发布；没有修改原通行证，没有生产执行授权。源 manifest SHA256：`2c1a45a81203f8a510e687f420cae64811de8e9b0e1622d9c54036f5316c95ec`。

| 源对象 | 待批准候选 SHA256 | 原批准候选 SHA256 |
| --- | --- | --- |
| yanshi 0.4.0 | `40be54c79d3575138990ca111ef2589f0128d6f13c3015fa0acdd9454b0be072` | `c40fe243a82ce1d850514919fa4da32644d17f3efae22e14026cba7d0d4f2f58` |
| kuafu 0.4.0 | `25375f3d48ac908e71e4197c9e8be7b3e8bb2126ca73b1951ca50094bc81dc42` | `a5b184a3a1b652cf8b302fb9b97886a760620c79c64f376722cc1e2df5d5041c` |

源路径基准为共工 framework 根，使用本机忽略配置定位；不提交机器绝对路径或共工框架本体。

完整清单对照表明文件集合未变，只有以下两份内容发生变化：

- `agents/yanshi/references/adaptation.md`：绝对参考路径改为框架根相对路径，说明只读、非随包依赖、缺失未知、不自动下载。当前文件 SHA256 `66e8d33c01d5fc225f3fbb71254825a01b5a0bdcbb412325f830a7738b861831`，原文件 `22592876713f323d3a8e32f334d47dddbe09c6fe6b429c992ba9d2fd54f5e8c8`。
- `domains/quality/provenance.json`：改用工作区 archive 相对路径并明确解析基准。当前文件 SHA256 `22f031d7da8efae72b7f99c6bcb0b0543c319ccddcde8860cd2b1be61e3d27e7`，原文件 `dd14206c63b6e1056bdada9d831943536b287f5d63f568cf333c3f86c144e6a6`。

两份 archive/v0.9 原件匹配原批准摘要；6 份质量模板的来源、目标及 policy 摘要一致；只读外部参考目录当前存在。Agent 入口未变，未新增权限、后台行为或工具绑定。候选验证、质量归属和未变化的 diting 正式准入通过；源整体正式验证仍报 `Admission subject mismatch`。

独立评价：框架边界、元衡 purpose/truth/economy/authority/adaptation/continuity、精简及适用验证通过，批准待用户。Foundation 基线 1.0，SHA256 `af0b14934f8998ac7e751475f8192f52adbeb3a26e3d709ee083bcbfeb42148f`；元衡 0.4.1；policy 0.9.0。事件 `agent_definition_change`，阶段 `local_definition_release`，范围仅 `local_agent_definition_only`。

## 批准后仍需执行的步骤

用户对上述两个明确候选作出真实决定后，才能生成绑定新摘要的源通行证，保留旧批准历史；共工原件继续留在源工作区，不入此 Git。随后使用现有 Olympus 同步工具在新目录完整重建候选，保持 Hermes 豁免，独立复核最终 Olympus 摘要，再提交本地 Agent 批准。源批准证据变化会改变本地摘要，不能提前用旧本地摘要替代。

批准定义发布仍不等于模型生产验收。真实宿主权限、有效模型配置、代表任务与采集回执必须分别验证。跨 IDE 宿主协议不改变以上要求。

## 宿主实现的独立审查

评价者 `/root/review_chat_gate` 已独立复核此次宿主协议、生产诊断、安装路径发现、安装摘要验证与准入链。初次运行 11 项测试，确认实际 doctor 报出四项准入阻断，且不声明模型执行或身份认证。建议的无环境覆盖安装探测和 doctor 阻断断言已落实；最终增量结果与文件摘要见 `integrations/godot/verification-host-portability-20261102.json`。

## 用户已批准源候选后的最终 Olympus 对象

用户明确回复“批准这两项已审候选”。源已登记真实决定、独立评价与绑定通行证，旧批准原字节保留。共工正式校验通过。使用当前同步工具在新目录全量重建后，部署 Olympus 与该目录逐文件一致，Hermes 扩展及根数据原样保留。

`/root/review_upstream` 再次独立复核：正式来源同步、候选验证、质量归属、13 个 reporting profiles 均通过。相对重建前仅来源索引、派生摘要、待审通行证和同步报告改变；Agent 入口与行为、宙斯治理、权限边界未变。Athena、Themis、Hermes 入口分别 873、888、825 字符。三者框架、宙斯六项原则、精简与适用验证评价均为 pass，独立性 `independent_subagent_review`。

| 最终对象 | 版本 | 候选 SHA256 |
| --- | --- | --- |
| Athena | 0.4.0 | `15750fcb9afeacf9ee5ee706caa291770344bda8e95b4411c603fd0966d0b83a` |
| Themis | 0.4.0 | `c41a33bd6d51ceb58cddc42f60583769f3726bf0f0d5945c9e11cee63cf08b1e` |
| Hermes | 0.4.0 | `f2abe1073b7721e3d0d860e531efb9fc99d41f3d43a038ffe55bee1f3e5324cf` |

基线：Foundation 1.0 SHA256 `e79a3a3ab5c4de36573d2c4835cf0fed9d05f672da52740ef0c2527dde1c0dce`；Zeus 0.4.1；policy 0.9.0；来源索引 SHA256 `1d94e7b92d83c0ef78d40e0f4068164410d86a1bcfc1fe70107e031539c6502a`；manifest SHA256 `c9d3317919373e4b43685adbc0c140ed2200716e60241ae5779c281bd287a2cd`。

用户随后明确回复“批准这三个最终候选”。真实决定已记录于 `Olympus/reviews/local-admission/user-decision-20261102.json`，独立评价与三个匹配通行证一同落地；正式框架验证与 doctor 均通过。事件、阶段和范围仍为 `agent_definition_change` / `local_definition_release` / `local_agent_definition_only`，有效性仅 `bound_candidate_only`。这不是对未来摘要的授权，也不替代模型账户、真实宿主权限与运行回执。
