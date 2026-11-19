# 生成服务分服务配置持久化与 offline 模式移除

<!-- gonggong-request:generation-service-profile-persistence-20261120 -->

## 生产工单

- Issue：#1624，https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1624
- 基线：当前 main 的候选分支，最终基线由正式提交门禁回读。
- 范围：生成服务设置、配置迁移及其回归测试；不新增或修改马良模块路由，不收录其他未提交的图像／网格改动。

## 用户目标

1. 删除生成服务的 offline 模式；本地复制节点继续可用。
2. 所有生成服务配置都持久化到本机文件。Kimi 切换到其他服务再切回，以及重开界面时，已配置内容不得丢失；服务未启动、未显式激活时也要保存。
3. 保留“显式保存后才激活运行配置”的边界，不把配置草稿自动变成生产运行配置。

## 实现

- 服务列表和后端配置校验移除 offline；复制专用运行快照改标为 local_copy，不依赖已删除的服务模式。
- 新增本机 `generation-service-profiles.json`，按服务模式保存独立配置及当前草稿选择。编辑和切换时原子写入，重开时恢复；原 `generation-service.json` 仍只保存显式激活的运行配置。
- 切换前保存当前服务草稿，切换后恢复目标服务的地址、模型、CLI／Blender／Kimi 工具路径及隐藏模型字段。配置不进入工作流，不保存凭据。
- 兼容旧单服务配置和退役 Codex 建模模式；未配置节点在首次保存服务时继承一次模型。
- 异步检测回执继续绑定精确草稿；过期回执不覆盖当前状态，并在设置区显示明确提示。

## 验收

- 验收: OFFLINE | 服务列表及后端不再接受 offline，本地复制节点和既有复制发布流程保持可用。
- 验收: PROFILES | Kimi、Codex、ComfyUI 等服务分别持久化，切换后各类配置正确恢复且互不覆盖。
- 验收: DRAFT | 未启动服务、未点击显式保存的草稿同步写入文件，重开界面后恢复；显式保存才激活运行配置。
- 验收: COMPAT | 旧配置迁移、异步检测、工作流配置隔离及统一设置重开回归通过。
- 验收: DELIVERY | AINative Python、Godot 配置界面和干净候选原生验收通过，正式门禁、PR、CI 和远端 main 回读完成。

## 验证记录

结果保存在 `data-collection/generation-service-profile-persistence-20261120-validation.json`。接口与合成夹具不构成真实模型推理证据；本单不涉及真实模型生成验收。
