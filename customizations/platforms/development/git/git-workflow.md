# Git 工作流接入子模块

工单：[Issue #9](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/9)。本模块属于 GongGong 宿主 `issue-workorders`，为后续共工/司南 GitHub 来源适配提供可核对的输入契约；它不注册 Sinan 来源，也不向共工宿主部署。

## 身份与并发记录

- 新建 Issue 时读取 `gh api user` 的认证 login，正文写入 `<!-- gonggong-host-git:LOGIN -->`。Issue 表单要求填写“宿主 GitHub 账号”。字段仅表示声明的责任账号；表单值和旧 Issue 不自动视为已认证。
- 单次显式事件以 `repository + issue + GitHub event ID` 生成稳定键。原始 envelope 记录事件 `actor.login`、当前 Issue `updated_at` 与正文 SHA256；`revision_marker` 标明该观察的键和认定边界。不同事件保留各自记录，不覆盖历史。
- 事件回读与 Issue 当前快照并非同一原子事务。宿主更新 Issue 前后应回读并比较标记；遇到并发变化时追加冲突记录，由实际责任人认定哪项更新生效。不得把最后读到的正文、提交作者或账号声明冒充唯一写入者。

## 共工后续补充

共工侧需在有效上游中实现 GitHub Issue 来源适配：绑定真实事件来源和认证账号，按同一稳定键去重，保存更新前后修订证据、执行账号、冲突与认定回执；将 followUps 与真实 Issue 查重关联，区分 proposed 和实际 start/ack。司南只消费其真实注册来源，元衡原账本和谛听采集协议保持各自权威。完成后按 GongGong 全量同步与精确准入流程更新 Sinan；本子模块的本地测试不能替代该步骤。
