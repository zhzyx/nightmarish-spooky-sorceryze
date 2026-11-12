<!-- gonggong-request:project-native-contributing-20261112 -->

# 将贡献指南替换为项目自有版本

## 用户目标与授权

用户于 2026-11-12 明确说明根目录 `CONTRIBUTING.md` 已没有长期使用价值，终极目标是去 Godot 化，当前仅是外壳。当前会话获得直接替换该文件、验证并交付的授权。

稳定需求 ID：`project-native-contributing-20261112`。

关联 Issue：[Issue #937](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/937)。

## 最新决定与范围

- 直接重写根目录 `CONTRIBUTING.md`，不采用“项目指南 + Godot 附录”的形式。
- 删除上游社区、翻译、功能提案、聊天链接、官方 Issue 链接及团队落款，不继续维护上游贡献流程的外壳。
- 新指南只面向本项目：独立架构方向、Issue 与设计、隔离开发、C++ 规范、验证、PR、第三方和归属文件。
- 保留并链接 `CPP_CODING_STANDARD.md` 与 `.github/CONTRIBUTING.md`，不复制其中的详细规则。
- 不修改 `AUTHORS.md`、`COPYRIGHT.txt`、`LICENSE.txt`、`thirdparty/README.md` 或其他归属、许可证文件；贡献指南不代替其声明。
- 除同步修正 `.github/CONTRIBUTING.md` 对根目录指南的一处描述外，不修改 C++、构建脚本、格式配置或其他文档。

## 验收条件

- 根目录指南不包含 `Godot`、`godotengine` 或上游团队落款，不保留上游社区、翻译和提案流程。
- 明确本项目贡献面向独立架构和逐步替换，不新增无必要的上游依赖。
- 保留项目 C++ 规范和仓库实际交付入口，所有相对链接有效。
- 指南简洁、可执行，覆盖开始前、开发、验证、提交和第三方边界。
- Markdown 结构、尾随空白、代码围栏、链接、上游残留和变更范围检查通过。
- 最终候选整合最新 main，正式门禁、远端检查、main 回读和 Issue 收尾完成。

## 验证计划与停止条件

检查新指南的项目指向、相对链接、上游残留和实际差异，并回读归属文件未被修改。纯文档变更不运行本地引擎构建，远端检查按实际触发核对。当前 GitHub 直连不稳定，先在已确认不涉及目标文件的相邻主线快照准备，提交前必须整合最新 main；若无法取得最新基线，不提交或合入。

## 执行与验证记录

- 根目录指南已从 226 行上游文档替换为 49 行项目自有指南，不包含 `Godot`、`godotengine`、外部社区链接或上游团队落款。
- 新指南覆盖独立架构、Issue 与设计、隔离开发、C++ 规范、第三方与归属、验证、PR 和交付完成条件。
- `.github/CONTRIBUTING.md` 仅同步修正根目录指南描述，未改变仓库治理流程。
- 58 项检查通过，覆盖相对链接、上游残留、必需项目规则、归属文件不变、Issue 关联、尾随空白、代码围栏和变更范围。
- 需求事件、来源索引及 `data-collection/project-native-contributing-20261112-validation.json` 已生成。正式门禁、远端检查、main 回读和 Issue 收尾在实际完成后记录于权威工单。
