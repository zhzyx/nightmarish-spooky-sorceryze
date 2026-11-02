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
