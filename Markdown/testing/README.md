# 测试与验证模块

本模块负责选择受影响测试、区分证据等级并如实记录结果。命令以实际引擎仓库根目录为工作目录。

## 验证原则

- 缺陷修复优先增加能复现原问题的回归测试；平台、并发、序列化和生命周期改动覆盖对应风险。
- 候选变化后重验受影响内容；旧候选结果不能自动套用到新二进制或新提交。
- 记录实际命令、运行环境、候选版本、结果和未验证项。未运行、跳过、环境不可用及失败均不得写成通过。
- 不用降低检查标准、隐藏告警或批量改写无关代码来消除失败。
- 纯文档变更不机械运行引擎构建，但应检查文档结构、链接和变更范围。

## 常用入口

| 范围 | 入口 |
| --- | --- |
| Windows 编辑器与 AIChat 回归 | 见 `../build/windows-editor/README.md` |
| AINative Python 契约与工具 | `python -m unittest discover -s tools/ainative -p "test_*.py"` |
| Gameplay 原生测试 | `<editor-binary> --headless --test --test-case="*Gameplay*"`，将占位符替换为本次构建的实际编辑器 |
| Engine Next 契约 | 见 `../build/engine-next/README.md` |

## 证据边界

- 合成夹具、模拟 HTTP、headless 测试、真实编辑器、真实供应商、人工视觉验收和发行包验收是不同证据等级。
- `completed`、命令 accepted 或路由成功只代表对应阶段完成，不自动证明异步业务完成。
- 像素、IME、系统原生窗口、外部认证和真实交互不能由结构化命令回执替代。
- 测试结果不能替代独立审查、正式门禁、CI、main 回读或业务验收。

原始说明见 [项目贡献指南](../../CONTRIBUTING.md) 与 [AINative 工具说明](../../tools/ainative/README.md)。
