# 多宝提交输入的 Git 管理路径保护

<!-- gonggong-request:tianxuan-audit-tx-01-20261114 -->

Issue：[#1115](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1115)。
父需求：[全工程 AI/Git 接入复盘 #978](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/978)、
[天璇 #1085](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1085)。
路径均相对仓库根；继承 [天璇平台设计](tianxuan-platform-20261114.md) 的仓库操作边界。

## 当前结论

用户已授权全工程 AI/Git 接入的审查、范围内修复与交付。原适配器 PR #1102 已合入；本 BUG 创建时无人认领且没有候选发布，本会话以 Sail-Li 身份负责独立修复。
不接管 #1085 的其他候选。五项定向测试、八项本机 Git 回归及独立审查通过；正式候选 CI、main 和原验收仍待回读，状态见 `data-collection/tianxuan-git-admin-paths-1115.json` 与原 Issue。

## 原问题与修订

`commit(files={".git/config": ...})` 的词法检查和工作区内路径检查都允许管理目录，写文件发生在 `git add` 前。隔离假进程复现确认配置被覆盖，不把此证据称为生产命令执行。

文件映射全部验证后才探测仓库或运行 Git。每个路径段保留 `.git` 管理名称，包括大小写、末尾点/空格及格式字符的代表性别名；已有绝对路径、冒号、反斜线和特殊字符拒绝继续生效。所有目标先预检，再写入：拒绝符号链接、可检测的 junction、越界路径，以及解析后落入管理目录的路径。普通文件替换与 `.github`、`.gitignore`、`.gitattributes`、Unicode 文档路径保持可用。

Git 命令显式关闭 hooks、fsmonitor 与 commit signing，落实既有模块声明；不覆盖全局 attributes 配置，不新增服务认证或后台进程。仓库所有者及服务配置继续属于可信边界，不声称提供任意 Git 配置沙箱或防御恶意本机并发写。

## 验收与证据

1. 直接管理路径及代表性别名输入在 Git 进程前被拒绝，配置不变。
2. 符号链接/解析后管理目录别名被拒绝，前置普通文件也不被写入；已有正常提交、分支、历史、差异、快进与冲突合并回归通过。
3. 独立审查绑定实际文件；正式门禁、精确候选 CI、main 回读与本 BUG 状态闭环完成后才报告交付。

本地平台为 macOS arm64，Python 3.14、Apple Git 2.50.1；测试只使用隔离本机仓库及 file 协议，不调用真实 Git 托管或模型服务。CI 沿已安装的 Tianxuan Module tests 和适用全库检查。Python 独立模块修复不改变 Godot 原生或嵌入资源输入，不为此新增引擎编译要求。真实 Windows/NTFS/HFS 文件系统未在本机验证；内部别名语义模型不证明远程 files 能构造 junction。

初次测试因 Git 向上发现外层仓库而失败，隔离测试目录后通过；独立合成仓库确认产品也接受普通子目录，此既有行为另由 [#1122](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1122) 跟踪，未混入本补丁。
首次 intake 因缺少 workspace 标签拒绝，补标签后原操作复验通过；不删除失败记录。召回 `github-issue-delivery/reconcile-workflow-incidents`：仅按同一动作和候选关联恢复，其他测试或其他 BUG 成功不代替本项验收。

## 回退与收尾

故障时保留错误和候选，沿正常 PR 回退本修复，不修改他人的工作树或有效安装。交付核验后归档必要证据、核实工作者终态，再正常删除本任务临时分支和工作树；未交付对象继续保留。其他范围内缺陷 #1116/#1117/#1118/#1122 分别验收，不因本修复关闭父单。
