# 编辑器安装暂存目录 Git 忽略

来源：[Issue #903](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/903)，请求 `editor-install-stage-git-ignore-20261112`；父项 #773，故障链 #807。当前操作者 Sail-Li 的既有编辑器安装与生产验收授权覆盖本缺陷。基线 `55e41ffb6dbe537c8bfc1fa2450ffc20fc1a040e`；持久路径均相对于仓库根。

## 范围与依据

唯一运行配置变化为 `.gitignore` 加入 `/project/godot/.editor-install-*/`。`tools/install_gonggong_editor.ps1:18` 在安装根 `project/godot` 下生成 `.editor-install-` 加无连字符 GUID 的暂存目录；原配置只忽略 bin、versions、安装清单与锁文件。根锚点和目录后缀限定安装器命名空间，不忽略 `project/games`、普通源码、相似普通文件或其他层级目录。该命名空间归安装器所有。

原始 `install895-probe.log` 的 Windows Restart Manager 回执记录 Git for Windows PID 20648，并列出 `.editor-install-36faf1ba7fa04a099a54db7439f41f9f/godot.windows.editor.x86_64.exe`。这是原失败调查证据；其瞬时 delete-access 探测为 true，因此不将该日志解释为持续占用的证明。父会话保留失败、回滚和恢复日志：本地 exclude 恢复及另一次独立网络恢复后，官方安装成功至 main979dfe27。该结果支持 Git 扫描暴露暂存文件的诊断，不证明所有历史安装失败具有同一原因。

没有新增模块，也没有原生输入或生成头变化。适用 Windows/Git 宿主，编译器不参与；不重建原生编辑器。安装锁、原子替换、回滚和真实占用拒绝代码均未修改；不杀进程、不改主安装或其本地 exclude。

## 方法召回与验收

已召回本租户 `godot-build-placement/trace-native-consumer` revision 14：按实际消费者确认本次仅为 Git 配置，不能因文件后缀判断原生依赖；其嵌入脚本反例不适用于本次。已召回 `editor-dependency-handoff/bind-consumer-release` revision 10：交接核对当前字节与回执，候选变化须重取证；子任务完成不等于安装或父项验收。方法反馈由父会话串行追加，避免并发修改经验链。

- 已完成：独立 `git init --template=` fixture，无 `.git/info/exclude`；清除继承 `GIT_*`，禁用系统/全局配置与全局 excludes。原配置下三种真实暂存文件可见，新规则下不可见，并由 `git check-ignore -v` 精确归因仓库 `.gitignore:439`。
- 已完成：游戏目录、普通源码、同前缀普通文件、其他层级同名目录均仍可见。证据：`data-collection/editor-install-stage-git-ignore-903.json`；实际本地验证脚本和完整回执：`bin/903-validation/validate_ignore.py`、`bin/903-validation/fixture-result.json`。
- 待发布者：独立审查、正式门禁、精确候选静态 CI、main 回读。
- 待发布者：正式规则在实际安装仓库生效后，仅移除本次拥有的本地 exclude 恢复块，保留原先用户配置；复验官方安装入口并核对清单、二进制与回滚边界。失败继续原链留证。

仅上述最后两项取得真实回执后才能完成 #903；不以此关闭 #773 或宣称父项全部生产验收完成。回退方式是撤回这一条 Git 忽略规则；不影响安装器事务行为。
