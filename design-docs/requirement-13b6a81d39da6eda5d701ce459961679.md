# 修复 Codex CLI 模型选择与刷新，并增加推理强度设置

<!-- gonggong-request:requirement-13b6a81d39da6eda5d701ce459961679 -->

需求整理：Yanshi / ClarifyFeature；原始输入摘要：`13b6a81d39da6eda5d701ce459961679c464936f0f3491b35d59a8bf02beba5d`。

在 Codex CLI 模式下恢复对话模型选择及模型列表刷新，并支持高、极高、Max、ultra 四档推理强度。

## 范围

- 排查并修复 Codex CLI 模式下对话模型不可选、模型列表无法刷新的问题。
- 增加高、极高、Max、ultra 四档推理强度选择，将所选强度传递给 Codex CLI。
- 核实四档强度与当前 Codex CLI 实际支持参数的映射；对不支持的模型或档位提供明确提示。

## 验收条件

- Codex CLI 模式下能加载模型列表、选择可用模型，并在后续对话中使用所选模型。
- 刷新操作能重新获取模型列表；失败时显示可理解的原因并允许重试。
- 提供高、极高、Max、ultra 四档强度；受支持的选择在实际请求中生效。
- 模型或 CLI 不支持某档强度时明确提示，不静默替换为其他档位。

## 待确认

- 若当前 Codex CLI 不支持 Max 或 ultra，是否接受保留对应选项但禁用并说明原因？建议如此处理，以确保界面显示与实际生效能力一致。

## 2026-11-07 修复范围及交付

关联 Issue #165、#217；本次用户在 Codex 报告引擎会话的 Codex CLI 刷新按钮无效，并要求所有模型可调整推理强度、CodeBuddy CLI 和其他 API 做类似支持；无法确认的适配保留 TODO。仅实现此明确范围，不改其他在途工作。

目标为 macOS arm64 编辑器（Clang，SCons），改动对其他平台保留 Node stdio 协议支持，未实测 Windows。Codex 改用 app-server initialize / initialized / model/list，只查询目录、不启动对话或推理；处理分页、超时、失败及停止。模型选择继续传递 model，强度按返回的 supportedReasoningEfforts 启用低、中、高、极高、Max、ultra，不支持或未知时选模型默认，不发送无效参数。按模型保存选择，按会话保留目录能力，Codex 请求映射到 model_reasoning_effort。

API 两种连接共用强度控件；服务目录显式提供 reasoning_efforts 扩展时按其能力启用，分别映射 Chat Completions 的 reasoning_effort 和 Responses 的 reasoning.effort。标准 /models 无通用强度元数据，不猜测第三方模型能力。CodeBuddy 原有模型刷新保留，其目录目前只有 id/name/description，ACP 强度能力及更新协议未确认，保留 TODO 和默认强度提示。用户已明确允许不确定部分留 TODO。本次不宣称 CodeBuddy 强度已可调，也不宣称所有 API 均支持能力查询。Codex app-server 与 exec 的自定义用户 provider 配置一致性仍需专门适配（TODO）；当前官方默认 provider 已实测。

验收：真实本机 Codex 目录返回 8 个模型；隔离编辑器后台实测刷新、high 可选、会话切换保持强度、Luna 的 ultra 禁用、非法路径失败可重试，以及两类 API 的声明能力/未知能力回退。Node 回归覆盖握手分页、隐藏与重复过滤、错误/超时、强度参数和模拟聊天实际 argv。无生产模型推理调用；真实对话返回内容不在本次证据内。编译与上述检查通过即停止扩展实现；交付仍保留原工单未验证验收，不将旧工单整体标完成。

接口依据：[Codex App Server](https://learn.chatgpt.com/docs/app-server)、[OpenAI reasoning](https://developers.openai.com/api/docs/guides/reasoning)。
