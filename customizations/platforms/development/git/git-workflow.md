# Git 工作流接入子模块

来源：[Issue #9](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/9)。本页定义身份与并发记录契约；实际来源绑定和派发见[当前宿主入口](../../../components/issue-workorders/README.md#当前来源与执行接入9-最终对账)，不重复部署。

## 身份与并发记录

- 新建 Issue 时读取 `gh api user` 的认证 login，正文写入 `<!-- gonggong-host-git:LOGIN -->`。Issue 表单要求填写“宿主 GitHub 账号”。字段仅表示声明的责任账号；表单值和旧 Issue 不自动视为已认证。
- 单次显式事件以 `repository + issue + GitHub event ID` 生成稳定键。原始 envelope 记录事件 `actor.login`、当前 Issue `updated_at` 与正文 SHA256；`revision_marker` 标明该观察的键和认定边界。不同事件保留各自记录，不覆盖历史。
- 事件回读与 Issue 当前快照并非同一原子事务。宿主更新 Issue 前后应回读并比较标记；遇到并发变化时追加冲突记录，由实际责任人认定哪项更新生效。不得把最后读到的正文、提交作者或账号声明冒充唯一写入者。

## 共工后续补充

本标题保留历史锚点。#9 时提出的接入需求已由当前宿主的 GitHub 来源与操作者入口承接；本段不是普通任务需另行升级或全量同步框架的前置条件。来源绑定、去重、修订回读、start/ack 与真实终态以本次宿主运行证据为准。未来若修改共享框架定义，另按对应精确候选治理；本地测试不替代准入或业务验收。
