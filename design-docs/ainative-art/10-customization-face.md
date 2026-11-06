# 10-customization-face 捏人捏脸与面部叠加

稳定需求 ID：ainative-art-10-customization-face-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：CharacterDNA 参数、形变修正、衣服再拟合、面部通道/口型/表情/注视仲裁。

验收：体型和脸型保存重开一致；极限参数校验；捏人后装备更新；身体动作与表情口型叠加，头颈写入无冲突。

前置：05-rigging, 07-garments, 08-motion-generation。

本次实现边界（2026-11-07）：Windows 本机 Godot，独立 CharacterDNA/面部仲裁模块与可操作面板；使用 Blender Studio Rain v3.3 官方 CC-BY 资产私有转换进行真实人脸验证，人工映射只适用于该版本，不声明任意生成脸自动适配。身体层拥有 head/neck；post-body 面部只写形态与眼睛。体型沿用 garments 的校准包络，重新从不可变基体拟合独立衣服并失效缓存。产物限本单 tools/ainative、samples/ainative-workbench 与本文，下载和实际证据存忽略的 runtime/customization。停止条件为极限拒绝、不可覆盖、版本重开一致、真实几何与两个时刻表情/口型叠加及头颈不冲突验证完成；不 commit/push/关单，由 root 整合审查。口型及注视使用明确人工序列，不声明音频 AI 已实现。

## 首版实际实现与边界

正式 `workbench.gd` 已接入 `customization_panel.gd`，保留原 garments、motion 和 #150 layering 入口，面板内有独立预览。可加载映射脸资产、修改体型/脸型、手工口型/注视、加载真实 MediaPipe 表情并选择帧、加载带 `motion_target_profile` 的已生成身体动画、重新拟合独立衣服、保存新版本及重开。状态显示操作结果，原始诊断留证据文件。

最终验收角色采用 **独立 Rain 真实人脸 + 已验收 UE4 原生身体**。`customization_assemble.gd` 在私有派生版本中隐藏原身体头部三角形，保留原生身体 Skin/bind，按明确装配 spec 对齐头颈位置、尺度与颈部过渡；脸部组件只绑定 body Profile 的 head/neck 两骨。支持 `Interop.load_scene` 的 `.tscn`/GLB 基体、显式 family/body_mapping、来源版本/authority、face_parts、face_scale/offset、head_hide_half_width、neck_cut_y 与颈部过渡校准参数。**只实测 UE4 原生身体**；生成 robot→UE4/Mixamo 基体与其他脸需单独人工映射和校准，不以接口存在宣称已验收。Quinn #202 未验收。

Rain 全身体控制 rig 的辅助骨/B-bone 关系不能用简单 FK 父链和权重折叠保真重建，早期 `ui-v7/v8/v11` 身体/衣服动态截图暴露撕裂与扭曲，未列为通过。源文件与失败证据保留；本单不宣称 Rain 全身生产 rig 完整重定向。最终只使用其实际头、眼、眉、睫毛、牙龈、舌、主发型八部件；横伸的原参考马尾不纳入首版装配，毛发系统由 #153 承担。

## CharacterDNA、FaceBinding 与组合顺序

`customization.gd` 的 `dna(source_sha, body, face, mapping_version)` 产生 schema_version=1 的不可变值，`revision=Interop.revision`。body 的 chest/waist/hips/depth 是无单位倍率，合法域 0.8–1.2；face_width/jaw_width/nose_width 为校准权重，合法域 -0.5–0.5。非有限值、布尔/字符串、未知维度、版本/修订不匹配在写入前拒绝。

资产级 FaceBinding 持 source_sha256、asset_sha256、mapping_version、语义 morph 映射、correctives、body_mapping、来源/许可及独立装配的 body_source/body_profile。重复语义目标、未知/缺失形态与非法 corrective 会预先拒绝，不能静默部分写入。Rain 的实际 rig 控制经 Blender 求值后烘焙 jawOpen、mouthSmile/Frown、browDown、eyeBlink 和四个 look 通道；脸型为明确人工语义形变，jawOpen×脸型双线性 corrective 补偿嘴部运动随脸型改变。不是给任意生成头自动加嘴、眼或表情基底。

组合顺序为身体 AnimationPlayer/Profile → 面部形态。稳定优先级仲裁逐通道混合，同优先级后输入覆盖；人工口型/注视高于捕获表情，同向竞争通道做有界归一化。头颈骨仍由身体唯一拥有，面部函数不调用任何骨 pose setter。实际 MediaPipe 输入复用 #149 的 `frowning-v1.json`（72 帧，真实推理产物）；口型/注视是明确人工控制，不宣称音频 AI 或本单重新执行推理。

`refit(base, profile, dna, path, spec)` 必须从不可变基体出发，沿用 `Garments.fit` 的独立来源 SHA/版本与校准 cage；派生 body 保留语义 morph 和显式 torso 遮罩，体型只作用一次。`garment_cache_key=Interop.revision({dna:dna.revision, profile:profile.revision, garment:spec, fit_version:'reviewed-axis-cage-v1'})`，保存时拒绝 `garment_fit_stale=true`。重新拟合保留身体动画及其时刻，不能累积旧衣服/辅助骨。最终参考 shirt 是 #148 开放背心，前胸开口是源设计，使用原校准 cage 与 `occlude_torso=false`，没有为填补开口扩大服装。非布料求解/动态无穿透证明。

给 #153：`scalp_binding.revision` 是 source/DNA/完整 FaceBinding（含静止几何 asset SHA）的静止绑定版本；`pose_revision` 另将仲裁 channels 纳入。正常表情不会使 rest binding/发根/LOD 缓存失效，脸型 DNA 或装配版本改变才需要重新绑定。几何坐标为 mesh-local，skin 随身体骨架，不能误认为已经输出世界坐标锚点。

## 来源与许可

官方来源：[Rain v3](https://studio.blender.org/characters/rain/v3/)；下载文件名 `rain-v33.zip`，包内文件名仍为 `Rain v3.3/rain_v3.2.blend`。页面和包内 ReadMe 明确 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。署名：**Rain Rig (CC) Blender Foundation | studio.blender.org**。已做语义形态烘焙、便携材质、独立头部装配与颈部过渡修改，不冒充官方原版成品。

源码归档 SHA256 `80217f163f6392dc829233d63c2cfb5e1376775bc34101ad14f39631fea70d24`；源 blend SHA256 `831ab6d837c679040285862b15dc9ee5180b018442a88aeaf92aaa7509b80258`。源 blend 未保存改写。Blender 4.5.3 LTS 便携发行包从 OCF Blender 镜像取得（官方主站请求 403），与镜像发行 checksum `6b657c8bdd3a7b65b07b9e1ae17eb4be7dd4aa23121da7f3d3354fc2551330a7` 一致；使用 `--disable-autoexec`，未安装系统服务或运行资产内自动脚本。

UE4 原生资产、既有 MDM 身体推理产物和独立生成衣服仅用于本机验收；各自来源/hash 分别保留在 FaceBinding.body_source、body_motion_source 和 garment manifest，**不发布专有资产**。权重、模型、源视频、全部二进制与本机 config 留忽略的 `runtime/customization`。版本场景不存本机基体绝对路径；重开时通过面板的本机 base 路径字段解析并核对 SHA。

## 实测与复现

基线已快进 #150 合入的 `a61963195b3f75471be6e6a7f6ba05f6073db35d`。Windows Godot `4.8.beta.custom_build.ced0368bb`，OpenGL compatibility / RTX 4070 Ti。主要验证入口：

- `customization_contract_tests.gd`：参数边界、无效值、通道仲裁、cache key 变化。
- `customization_geometry_tests.gd -- <private-config> <new-receipt>`：实际导入资产双端边界，Godot 原生 morph 烘焙顶点有限性、真实位移、rest/pose 版本分离。
- `customization_live_ui.gd -- <private-config>`：从正常 workbench 查找 panel，而非临时注入；真实来源→控件→重拟合→身体动画+脸→原子保存→重开→再次拟合。
- `rain_convert.py` 由便携 Blender 在私有源 .blend 上执行；`customization_assemble.gd -- <private-spec>` 生成独立头部/身体派生基体和外部 FaceBinding，不覆盖任何源。

当前组合证据为 `runtime/customization/ue4-final-v3-*.png` 与 `ue4-final-v3-receipt.json`，包括两时刻工作台、同时间同 DNA 的无衣/穿衣全身正侧视图及颈部侧视图；裸身对照从真正 immutable base 重建，未误用已遮罩派生体。身体真实 head 全局移动 2.529109m；面部前后 68 骨 pose 完全相同。独立背心两体型的实际顶点最大变化 0.034689m，源 SHA 保持；cache key 改变。rest cage 抽样 5976 条身体边无交叉，9 个距衣物表面不足 3mm 的抽样点仍如实保留；不将抽样等同穷尽或动态碰撞证明。

`ue4-geometry-v1.json` 两端各烘焙 25777 顶点全有限，最大实际 morph 位移 0.137866m；表情变化只更新 pose_revision。保存采用既有 `interop_publish.py` 的临时完整文件 + 原子 hardlink no-clobber，重复目标明确拒绝；DNA/morph/身体动画在 PackedScene 和实际面板重开后一致，再次 refit 保留 body animation 且衣服数仍为一。候选独立审查与精确交付由 root 汇总，未自行提交/推送/关单。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。

最终窄回归：当前面板先选择捕获 frame71，再重开保存的 frame0 版本，保存 layers（按既有 float32 revision 规范）、pose_revision 和 156 morph 状态恢复。旧 final-v2 的严格双精度字典比较因 .tscn 十进制回读舍入失败，保留日志；修正比较方式后的 final-v3 exit0 且无 Godot 错误。独立审查另核对原生 UE4 68 骨、68 Skin bind 与 7147 身体顶点/权重/骨索引，八个人脸部件 18630 顶点只含 head/neck 影响；重复映射、失败加载保持旧实例、重复载入 BodyMotion 节点命名、只作用一次、重开/refit 与 no-clobber 均有定向真实回读。
