# 多宝 Git 操作的精确仓库根校验

<!-- gonggong-request:tianxuan-repo-root-validation-20261114 -->

关联 [#1122](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1122)、父需求 [#978](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/978) 与 [#1085](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1085)。路径基准为仓库根，继承 [天璇平台设计](tianxuan-platform-20261114.md)。

## 问题、责任与修复

`_repo_path` 原先只执行 `rev-parse --is-bare-repository`，Git 向上发现使普通子目录也通过校验。合成仓库复现 status 返回父仓库信息，branch 修改父仓库引用；没有操作用户真实仓库。原 7 项测试的 41 个失败子断言包含前置写入后的级联，不能视为 41 个独立缺陷。

本会话在原全工程修复授权下接收新建且无在途发布的独立 BUG，原实现工作者完成后由另一工作者审查。当前操作者通过阎罗承担本批发布与协调，不接管 #1085 的其他候选。

新增根探针：普通仓库取得 `--show-toplevel`，裸仓库取得 `--absolute-git-dir`，与输入规范路径比较。拒绝普通/深层子目录、裸仓库内部目录、linked worktree 子目录及非根的符号链接；合法 ordinary/bare/linked/symlink 根保持可用。失败发生在后续业务操作之前。

第一轮独立审查发现路径中 CR/CRLF 被 Python 文本模式归一化而误拒绝。修订为仅根探针选择原始字节捕获，再按既有 UTF-8 契约解码，保留路径换行，仅去除 Git 追加的单个 LF。其他 Git 调用仍沿用原文本行为。新增 CR、CRLF、LF 与末尾换行路径回归。根探针每次校验增加一次 Git 进程，未新增重试或后台扫描。

## 验收

1. 根与子目录按实际 Git 仓库边界区分；普通/裸仓库及 linked worktree 根通过。
2. 路径规范化、符号链接根和合法 POSIX 换行字符兼容；Windows 禁止的 CR/LF 文件名用例明确跳过。
3. 非根输入被共享操作拒绝，父仓库引用及工作区内容不变。
4. 原 Git 操作和 #1115 管理目录保护与本修复共同通过回归、独立审查、正式门禁、精确 CI 与 main 回读。

本批与 [#1115](tianxuan-git-admin-paths-1115.md) 合并为一个相关 Git 路径候选，基线 ec91084725ff34bc7f486a25be8804d078491f4e。当前本机 21 项测试通过（原 8、管理路径 5、根路径 8），只有本机合成 Git/file 协议实测。Windows/Linux 原生路径语义尚未在本机验证，CI 按其实际覆盖记录；不声称完整 Git 配置沙箱或防御恶意本机并发写。

状态与证据见 `data-collection/tianxuan-git-paths-integration-1115-1122.json`。独立审查、CI 和 main 必须有实际回执后才报告交付；父需求剩余范围继续保留。旧修订及失败记录保留。交付与工作者终态核实后清理本任务临时文件、分支和工作树，保留未交付改动及其他任务资源。
