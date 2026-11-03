# P4V 借鉴与 Git 映射

核对日期：2026-11-03。以下为官方资料的概念总结与本项目设计映射；没有复制实现或安装 P4 Server。

| P4V / P4 概念 | 哈耳摩尼亚在当前 Git 工作流中的做法 |
| --- | --- |
| Pending changelist 将一组待提交文件归在一起 | change_id 对应 Issue、当前账号、基准与文件清单；实际 Git 暂存内容仍须核对 |
| Reconcile 找出工作区新增、修改、删除并选择纳入 | 比较 status/diff/改名与认领范围，精确纳入自身内容，保留无关修改 |
| Shelve 保存待审改动但不等于提交到主线 | 自身补丁/分支/draft PR 作为交接；stash不是共享存储 |
| Resolve / P4 Merge 使用共同基准比较 | 在自己的本地副本保留三方差异，解决冲突后做语义验证 |
| p4 lock 与 +l exclusive-open 不同 | 前者限制别人提交，后者限制并发打开；Issue评论两者都不等价，不能当强制锁 |

官方资料：
- [Changelist 与提交](https://help.perforce.com/helix-core/server-apps/p4v/current/Content/P4V/files.submit.html)
- [Reconcile offline work](https://help.perforce.com/helix-core/server-apps/p4v/2026.1/Content/P4V/using.offline.html)
- [Shelve files](https://help.perforce.com/helix-core/server-apps/p4v/current/Content/P4V/files.shelve.html)
- [P4 Merge](https://help.perforce.com/helix-core/server-apps/p4v/current/Content/P4V/advanced_files.p4merge.html)
- [Preventing multiple checkouts](https://help.perforce.com/helix-core/server-apps/cmdref/current/Content/P4Guide/resolve.lock.exclusive.html)

Git映射是本项目的协作设计，不宣称 Git 原生实现 P4 服务器的文件检出/锁与变更集语义。只使用既有 Git/Issue 能力，不引入跨机器开发或远程工作区控制假设。
