# CLI 静态检查修复

关联 [Issue #11](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/11)，稳定需求 ID `restore-repository-ci-20261102`。范围是该工单后续格式检查中的 CLI 部分；不代表整个 CI 工单完成。

原 #11 已按其原始 CI 恢复范围完成并关闭。此前留在隔离工作树的两处 CLI 格式修复现由 [Issue #39](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/39) 承接，稳定需求 ID `codebuddy-cli-lint-20261104`，宿主 Git 账号 `Sail-Li`。下方 #11 来源和事件保留原始身份；本次交付追加 #39 的独立请求与验证事件，不改写历史。

用户要求更新仓库并检索 CLI 修复，已核对主线 `a3ac6b19` 恢复的 CLI 桥接与锁定依赖。历史 CLI 关联工单 #2、#3 已完成，开放的 #7、#8、#9、#11 各有其他验收项，不能因 CLI 回归通过一并关闭。执行者为当前 Codex 主任务，未作为已启用的 Olympus Agent 执行。

在隔离分支 `codex/cli-fixes-20261103` 修复：恢复提示的英式拼写改为仓库要求的美式拼写；codespell 仅新增 `tools/codebuddy_cli/package-lock.json` 排除项，与既有 Web 锁文件规则一致。其完整性哈希中的随机字符是误报，保留锁文件字节与依赖版本。未更改模型权限、传输或恢复流程。

实际验证：

- 按 lockfile 执行 npm ci，禁用安装脚本，成功安装 102 个依赖包。
- `node --test tests/editor/test_codebuddy_bridge.js tests/editor/test_codebuddy_acp.js`：43/43 通过，包括大流量、输出限额、取消相关进程清理、恢复、权限和隔离。
- codespell 2.4.2 对三个 CLI 源文件、package.json、package-lock.json 和 pyproject.toml 检查通过。
- 仓库 file_format 检查和 git diff --check 通过。
- 正式 verify_framework 校验通过，冻结纲领不变；该结果不认证宿主权限。

首次执行完整三个测试文件时缺少依赖和 Git Bash；补齐依赖后复跑上述 43 项成功。终端测试依赖的 Git Bash 在当前宿主不可用，未声称终端套件通过，也未调用真实供应商账号。无业务逻辑变更，不新增镜像测试。

GitHub 插件创建 CLI 专项 Issue、更新 #11 状态均返回 HTTP 403 Resource not accessible by integration。专项单未创建；本修复复用已存在的 CI 工单 #11，其远程状态仍为 in-review。远程文档互链、完整 CI 验收与正式合入仍待完成，不关闭 Issue，不冒称已提交或已发布。主工作树由其他聊天执行中的合并与暂存内容保持不动。

Hermes 校验及 git-check 通过：34 条记录、37 个数据文件已跟踪。使用主工作树受信任 issue_gate.py 对隔离候选检查，主线 work-items.json 缺少 tenant_id 绑定而拒绝；本分支不复制其他聊天在途治理修改绕过检查。尚未提交，不能运行提交后校验来宣称交付完成。

独立只读审查由 `/root/cli_review` 完成，无阻断发现，确认锁文件未修改，检查范围仅为两处代码/配置差异。审查者未独立复跑测试，采用主任务的执行证据；不解除上述门禁与完整 CI 限制。候选摘要见 [审查记录](../data-collection/cli-ci-review-20261103.json)。

## #39 当前基线复验

隔离分支已快进至 #9 子模块合并后的 main `54c7796d`，只恢复上述七个暂存文件。当前 Windows 宿主上 CodeBuddy bridge/ACP 43 项测试和正式 Olympus 校验通过，Hermes 文件事件验证通过；代码及配置仍仅改恢复提示拼写与 CLI lockfile 的窄范围 codespell 排除。提交、远端 CI 与合入以本单实际门禁和回读记录为准。
