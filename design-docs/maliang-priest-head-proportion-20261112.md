# 人形模型头身比例修正与验收规范

<!-- gonggong-request:maliang-priest-head-proportion-20261112 -->

日期：2026-11-12（Asia/Shanghai）。路径基准：仓库根。关联 Issue：[#955](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/955)，前序 #944。稳定需求 ID：`maliang-priest-head-proportion-20261112`。

## 需求与范围

用户复核全身后指出头部比例偏大，要求重新调整，并记忆人形模型验收方式，形成 Markdown 验收规范。当前任务不是重新生成角色，而是对已验证的减面模型进行局部比例修正，同时保留脸型、五官材质、身体与 T Pose。

## 修正方法

- 以 `workflow-preview/head-reference/merged-priest-decimated.glb` 为源，源 SHA-256 `3a82cc56b0fbee9fde718ba596688355d16cbe7e4353cfc10a220fc654e8fa5c`。
- 新文件 `workflow-refined-preview/priest-head90.glb`，输出 SHA-256 `f9cae5780696a8c5d88fa765d66295ffbf9900a6df58fe0c31c685fdc62556d7`。
- 头部整体缩放 0.90。颈部世界基准 `neck_y = 0.34`，转换到节点本地基准 `[-0.030569089576601982, -0.09895345926284788, -0.023940416052937508]`。减面服务会重置头部原点，不能直接对世界 Y=0.34 的本地顶点缩放。
- 仅修改 `ReferenceHead` 网格位置及 POSITION accessor 的 min/max。法线、材质、索引、身体和源文件不改变。
- 修正后比例约 14.5%，635,471 vertices、1,200,135 triangles、39,638,400 bytes。该比例只适用于当前角色，不是通用审美阈值。

## 验证

- 独立 GLB 结构与 `validate_mesh` 通过；索引未越界，顶点数未变。
- 最终严格零面积三角形为 0；最终头颈区域 387,548 triangles，微小三角形不直接等同于破洞。
- 真实 Godot 渲染全身正面、斜侧面、背面、正脸和斜侧脸；比例较上一版自然，头颈衔接未见明显异常，法袍、肩甲与 T Pose 保留。
- 原生资源保存和重开通过，源模型未被覆盖。
- 新模板 `priest-head90-adjust.json` 内嵌修正后的 GLB，恢复和运行前检查通过；打开不自动提交生成任务。
- 可复用验收清单见仓库根 `human-model-acceptance.md`。本文及清单记录实际证据与限制，不宣称通用自动换头、完美相似、生产无缝拓扑、绑骨或动画能力。

## 边界与交付

模型、模板和原始人脸是本地交付物，不提交大文件或隐私素材。公开证据只含设计、统计、操作 ID、摘要和必要恢复记录。没有新增 Provider、节点或通用自动头部替换承诺。
