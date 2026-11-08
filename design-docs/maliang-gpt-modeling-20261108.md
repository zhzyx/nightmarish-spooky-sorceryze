# 马良：GPT CLI 建模指令与原生 Mesh 节点预览

<!-- gonggong-request:maliang-gpt-modeling-20261108 -->

用户在当前 Codex 会话明确选择：仅使用 GPT CLI 输出建模指令或代码，由 Godot/Blender 构造网格；不依赖 ComfyUI 或专用本机三维生成模型。2026-11-08 追加要求保留现有节点化功能、连线、上下文、逐节点运行预览与工作流。

本轮交付 Windows x64/MSVC：新增独立 Codex 指令建模模式，图像生成仍用既有 CLI 图像能力；文字/参考图到网格通过 CLI 的结构化 JSON 建模计划，交给 Godot 的固定原语构造器输出 GLB。模型输出不作为可执行脚本。首轮覆盖有限原语组合和材质/变换；不承诺复杂人物、骨骼、动画或任意 Blender 脚本。保留旧模式与历史运行，不迁移其指纹或回执。

验收：无 ComfyUI 服务/权重前置；真实 CLI 返回计划；Godot 生成非空 GLB，原生节点预览、保存重开、发布通过；图像节点和旧模式回归；非法计划、失败/取消与恢复保持真实终态。通过局部测试、独立审查与正式交付路径后更新可测试引擎。达到一个真实节点闭环即停止扩展能力。

关联工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/543。

本地验收：真实 CLI 返回33部件计划，Godot 输出5610顶点 Mesh，连接至下游复制节点的预览、发布、保存重开全部通过。19项新后端/服务、48项新控件、25项构造器和6项独立CLI构造检查通过，旧Codex19/服务11/表单37/预览35及四组原生内置回归通过。Python静态检查与两个独立源码审查通过；完整来源摘要、实际CLI用量与失败保留见 data-collection/maliang-gpt-modeling-20261108-validation.json。远端交付未回读前不记完成。

提交前主线推进至fa6386c6，已整合并重新编译。五个建模运行文件与真实CLI验收完全一致，独立增量审查通过；新二进制四组原生回归、配置恢复、既有真实网格和节点连线重开及截图检查通过。不重复付费请求，不把旧二进制的实测重标为新二进制。证据：data-collection/maliang-gpt-modeling-20261108-integrated-validation.json。
