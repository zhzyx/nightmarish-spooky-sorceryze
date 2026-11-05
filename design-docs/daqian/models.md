# 大千 · 多供应商 API、能力评分与凭据

需求 ID 为 daqian-models-20261105。父级需求为 daqian-workflow-20261105，条款见 [完整设计](../daqian-workflow.md) 的「模型与执行」。相对路径以本文目录为基准。当前聊天负责本次实现与证据，交付目标为仓库 main。

## 范围

接入 Claude、DeepSeek、Gemini、GPT 和兼容端点；支持节点内新增配置、系统凭据、司南实测评分选型及手选覆盖，保留选择依据与执行记录。

## 验收

四个家族真实调用。视觉型号读出未在提示中透露的图像内容。验证能力筛选、无评分回退、恢复自动与停止后重跑。禁止把凭据写入图档或测试记录。

前置依赖为图编排契约。原生父子工单关系、候选与接收回执由父级档案统一追溯。

父工单 https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/119
