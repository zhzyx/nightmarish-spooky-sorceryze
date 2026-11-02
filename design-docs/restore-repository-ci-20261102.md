# 恢复仓库静态检查

工单：[Issue #11](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/11)。稳定需求 ID：`restore-repository-ci-20261102`。

实际执行：当前用户授权的 Codex 主任务，工程层维护；保留 Olympus 准入和原始事件。该项解除 #6 / PR #10 的 CI 依赖，不代表服务器分支保护已经启用。

1126 个已跟踪文件与忽略规则冲突，逐文件摘要在 `data-collection/issue-11-tracked-input-audit-20261103.json`。

| 分类 | 决策与原因 | 来源/生成入口 |
| --- | --- | --- |
| 1119 个 Mono API 源文件/包含清单 | 保留已交付快照；GodotSharp 项目直接引用这些文件，当前未验证同版本 .NET 重建，不以推测删除 | `modules/mono/editor/bindings_generator.cpp`；Mono 编辑器 `--generate-mono-glue`，见 `modules/mono/README.md` |
| SDK 版本属性与源生成器常量 | 保留版本快照，与现有 C# 项目配套；只允许具体文件 | `modules/mono/build_scripts/build_assemblies.py` |
| custom.py | 保留现有引擎构建输入，ANGLE 配置影响链接行为 | SConstruct 自动读取；纠正“未跟踪”的陈旧注释 |
| cpp.hint | 保留随引擎交付的宏解析提示，不是编译产物 | 仓库中的宏定义 |
| 历史验证 JSON | 保留已有交付证据；只允许该 JSON，不开放二进制目录 | 既有发布记录 |
| C# 示例 NuGet.Config / solution | 保留可运行示例的配置入口 | 示例工程 |

仅在相应目录增加窄范围例外；API 快照限 `.cs` 和 `.props`，其他构建结果仍忽略。没有关闭 gitignore_check、跳过失败或删除所有匹配项。后续执行干净检出下的原始 gitignore_check 和实际格式检查；远程精确候选、独立审查与真实事件满足前保持未完成。

进一步实际执行发现原脚本将全部路径展开为命令参数，在 Windows 干净目录报 `Argument list too long`，却因捕获空输出继续返回成功。本次修正为 `git ls-files -z` 经 stdin 送入 check-ignore，保留显式例外语义，失败状态明确传播，不用空输出冒充通过。实际检查覆盖 Git 已跟踪文件，避免工作区缓存干扰；独立负例验证真实忽略文件与命令失败均拒绝。

后续格式检查按仓库锁定的 ruff、mypy、clang-format、codespell 与 validate_includes 执行；修正导入/格式、测试 ModuleSpec 非空检查及 C++ include 路径。补充工程新增目录的 CODEOWNERS，保留原校验要求的 Godot 角色条目；CODEOWNERS 不是服务器权限或强制保护。完整 prek 依赖下载遭遇网络错误，远程精确候选结果另行记录，不用单项通过替代整条 CI。

## 2026-11-03 远程检查与分工

候选 `b439d03297dfed788b35d2634c9e9e2372fe2802` 的 PR 检查 [41486751907](https://github.com/zhzyx/nightmarish-spooky-sorceryze/actions/runs/41486751907) 已通过 gitignore、clang-format、ruff、mypy、CODEOWNERS、include、版权和文件格式检查。仍失败于 gitignore 检查脚本的可执行位，以及合并主线 CLI 文件时的 codespell 检查；平台构建因此未执行。

本任务补上 `misc/scripts/gitignore_check.sh` 的 Git 可执行位。用户随后明确 CLI 修复由其他人稍后提交、当前暂不处理；本任务已撤回对 CLI 提示词拼写及其 package-lock 拼写排除的未提交修改，保留主线原始 CLI 内容。等待 CLI 负责方交付后再验证最终合并候选；不跳过失败检查、不强制合并，也不将本单提前关闭。

## 批准框架的原字节校验

#7 的已批准分发包含上游既有的 Python 风格、类型标注和换行约定；直接运行 Godot 自动格式化会改变候选摘要。独立检查确认旧框架也存在这些差异。因此工程层增加 `tools/check_olympus_distribution.py`，用 `integrations/olympus/frozen-distribution.json` 固定全部非豁免分发文件的路径和 SHA256；它拒绝缺失、额外文件、字节变化、不安全路径、链接及候选/通行证内容不一致，并解析 Python、JavaScript 和 JSON 语法，不运行框架代码。

仅 Ruff 风格、Godot mypy 契约与 file-format 对这部分镜像采用上述强制校验；Hermes 独立扩展继续进入原有检查，其语法也由新检查覆盖。CODEOWNERS、shebang 及适用拼写检查仍保留；新增 check_delivery.py 登记 Git 执行位。镜像清单必须随新候选独立审查，不能自动重生成后当作授权。该 CI 结果只表示已登记快照自洽，不认证来源、批准者或运行权限；本机正式上游和准入检查仍由 Issue 门禁执行。

本机实际运行 11 项隔离测试，其中 10 项通过，真实 symlink 用例因 Windows 权限不足跳过；reparse 检查分支另有测试。136 个冻结文件一致，19 个 Python、11 个 JavaScript、51 个 JSON 语法通过。仍有两处未变上游文件的全量 codespell 历史差异，本次未放宽拼写检查；不宣称仓库全文件检查全部绿色。
