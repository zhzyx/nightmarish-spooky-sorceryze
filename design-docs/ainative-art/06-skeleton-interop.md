# 06-skeleton-interop UE 与 Mixamo 骨骼兼容

稳定需求 ID：ainative-art-06-skeleton-interop-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：独立版本 Profile；语义映射、参考姿态、骨轴、根运动、辅助骨、模型重绑与动画重定向。

验收：UE4、UE5 Manny/Quinn、Mixamo 各有授权测试夹具；模型目标绑定与双向动画重定向分别验收；接触/根运动/手指检查；导出经目标工具回读。MetaHuman Body 单独扩展，面部不计入身体兼容。

首版范围调整（2026-11-07 用户明确批准，根任务记录正式回执）：本次交付验收 UE4、UE5 Manny、Mixamo。Quinn 保留独立待验收项，不宣称实际支持，不以 Manny 代验；上述原始完整目标继续保留供后续追溯。

前置：05-rigging。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。

## 实现与操作

`samples/ainative-workbench/addons/ainative/interop.gd` 独立实现实际资产导入、Profile 提取、参考姿态重绑、动画重定向和导出。Godot 工作台的 Skeleton interoperability 区域可选择源 avatar、目标 FBX/GLB 或已保存 Profile，填写来源 authority/version，修改语义映射，预览骨架，适配网格、播放动画，保存新 `.profile.json`、`.tscn` 或导出 `.glb`。着地区间用独立 JSON 输入，例如 `{"squat":[{"side":"l","start":0,"end":2},{"side":"r","start":0,"end":2}]}`；可指定目标米制 `position_m`。未知着地区间不会自动宣称接触通过。

Profile 的 family 分为 `ue4`、`ue5_manny`、`ue5_quinn`、`mixamo`，语义规则版本为 `1`；`anatomical` 仅表示 #146 的源模板。规则只定义语义别名，完整骨架必须从所选实际参考文件提取。UE4 与 UE5 脊柱语义独立；Mixamo 支持冒号 namespace 与 Godot 导入后的 `mixamorig_` 前缀。twist、IK 和其他辅助骨保留实际层级/local rest；没有对应语义的带权骨折叠到最近已映射祖先并在诊断中声明。MetaHuman Body 未实现，属于单独扩展。

Profile 保存全骨名、parent、local/global rest、导入后单位/坐标声明、语义修正和不可变来源 SHA256/version/authority。Transform3D 按三个 basis 列和 origin 的 12 数排列。输入经过 Godot FBX/GLTF importer 归一到米制；FBX/GLTF 导入时把 Skeleton 祖先的旋转及正均匀缩放烘焙到根 rest 与根动画轨道，并记录 import_normalization；非均匀/镜像缩放明确拒绝。直接传入的未烘焙场景仍拒绝非 identity 祖先，避免把缩放坐标误称米制。Profile 校验父级范围、循环、有限可逆矩阵、local/global 一致性及必要语义。revision 绑定全部内容；数值按 Godot Transform3D 的 float32 精确位模式规范化，并对所有类型加标签，消除 JSON 浮点解析 ULP 差异与结构类型碰撞；引擎精度内的实际变换变化改变 revision。更改姿态/拓扑/修正必须形成新 revision。机器文件路径仅存在本地 UI 与测试配置，不进入 portable Profile。

Avatar 与 Skeleton 分离。目标重绑先根据语义骨段几何方向/长度建立参考姿态变换，使用源真实 Skin inverse-bind 恢复源 rest 下的顶点和法线，再进行目标参考姿态/比例变形与权重映射，最后生成目标 Skin。源没有手指时不凭目标空权重手指骨声明支持；diagnostics 单独列 `missing_source_fingers` 与实际 `weighted_finger_vertices`。绑定成功的状态是 `target_bound`，提取语义仅为 `semantic_mapped`，Godot 回读不自动升级为目标工具 `roundtrip_verified`。

动画以源模型空间 rest rotation delta 转换目标旋转，保留目标骨段长度，以髋至脚距离比例转移骨盆/根位移。无源 root、目标有 root 时从髋水平位移提取目标根运动；无目标 root 时位移由 hips 承担。显式着地区间使用解析两骨腿 IK，保持足部朝向，记录不可达误差。未声明区间的舞步或走路不能被当作全程锁脚。接触、动画来源和算法版本参与 Avatar revision。实现参考 [Godot 骨架重定向概念](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/retargeting_3d_skeletons.html) 和 [UE IK Rig 重定向概念](https://dev.epicgames.com/documentation/en-us/unreal-engine/ik-rig-animation-retargeting-in-unreal-engine)，没有复制 UE 实现。

`tools/ainative/interop_publish.py` 复用既有 `publish_new` 原子不覆盖发布，发布前检查 TSCN/GLB/Profile 编码，源字节不被修改。工作台发布前重新检查输入 SHA256。已发布资产需用新文件名保存修订；输出保留内嵌 Profile、输入版本和算法诊断。目标工具回读由独立验收证据记录，不由名称匹配或发布动作冒充。

## 验证入口与证据边界

- Python：`python -m unittest discover -s tools/ainative -p 'test_*.py'`，保留原 55 项并增加 interop 发布完整性/不覆盖测试。
- Godot 契约：`godot --headless --path samples/ainative-workbench --script interop_contract_tests.gd`，仅验证算法契约，合成骨架不计入 UE/Mixamo 兼容验收。
- 实际资产：`godot --headless --path samples/ainative-workbench --script interop_acceptance.gd -- <absolute-config.json>`。本地配置包含 `report_path` 与 `cases`；每项包含 `id/source_path/target_path/source_family/target_family/source_provenance/target_provenance/output_prefix`，可指定 `source_corrections/target_corrections/contacts/target_contacts/target_motion_path/target_motion_provenance`（独立动画文件单独提取实际 Profile 后重定向，不能用 Manny Simple 的动画附带网格替代完整 Manny 目标）。provenance 要有 `sha256/version/authority`；独立动画文件必须提供自己的 `target_motion_provenance`，不能继承目标参考资产的来源。路径仅留在忽略的本地配置；报告输出版本摘要和实际测量。
- 脚本分别测试源 avatar→目标重绑、源动画→目标、回程动画与目标原始动画→源。GLB 回读核对名称/父级/rest/轴、Skin、权重、动画时长/轨道，着地区间断言脚踝 <3 mm、实际鞋底顶点 <5 mm；未提供区间的动画只报告运动值。

实施中已在实际 three.js 示例 `Samba Dancing.fbx`（固定提交 `a75739a7ae5f2c08d1d9f3e2e4ac27fdceee83de`）提取 67 骨；robot→Mixamo 22,897 顶点实际重绑和 Godot GLB 回读通过。实际 UE4 模板 walk FBX 提取 68 骨，robot→UE4 同样通过；两者均使用原 robot squat 0–2 秒双脚着地区间，脚踝/鞋底误差低于上述阈值。Mixamo 实际源含 11,986 手指权重顶点，Samba→UE4/Manny 以及返回 Mixamo 的局部手指相对首帧活动约 0.856 rad；冻结手指局部姿态而保留同帧掌部运动的对照，测得手指自身引起的蒙皮位移分别约 0.114/0.087 m，回程约 0.113 m。静止姿态偏离 rest 不计作动画；robot 无手指蒙皮，报告明确保留 0。根运动按源 clip 水平位移×目标比例比较，阈值 2 mm；手指活动幅度容差 0.01 rad。

完整 Manny 目标实际为 161 骨，已通过同类 Godot 验收。Quinn 尚无来源已核实的实际夹具，仅有独立 Profile 语义规则，未验证；不能把 Manny 当作 Quinn 的验收替代。按用户批准的首版范围，Quinn 转为独立待验收项，由根任务记录后续工单；本次 UE4/Manny/Mixamo 的交付仍须完成独立审查与公共回执。专有 UE 原始资产及导出仅存忽略 runtime，不提交仓库。

真实 UE 对照发现一个必须保留的边界：UE5.8.3 导出的 UE4/Manny FBX 经当前 Godot FBX importer 后，所有全局骨帧相对原生 UE 有恒定右乘 +90° X 的差异，虽然层级和关节位置接近一致。原生 UE GLTFExporter 导出的 `*-native.glb` 直接回读 UE 则保持原生骨帧（控制实验最大旋转误差约 1.26e-5/4.46e-7 rad）。因此精确 UE 原生绑定使用实际原生 GLB 作为参考；FBX 可作为实际动画来源，但不自动宣称其骨轴等同原生 UE，且实现没有全局硬编码扭轴。已基于原生 GLB 重新生成 UE4/Manny robot 绑定并通过 Godot 深回读，UE 最终回读已实测 UE4 68 骨 / Manny 161 骨全部父级一致，原生 rest 位置最大误差约 0.000113 / 0.000072 cm、旋转误差约 5.64e-7 / 7.43e-7 rad，各 22,897 顶点和 3 个可采样动画，详见根任务公共证据。


## 最终首版验收记录

58 项 Python 测试、Godot 契约、独立真实资产复核和三套工作台完整回放通过；最终 UI 比较两个时刻的实际骨骼姿态，保存重开及不覆盖发布均通过。公共证据为 `data-collection/ainative-skeleton-interop-validation.json`。Quinn 后续 [#202](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/202) 与 [设计](06-quinn-validation-followup.md) 保留未验收范围；用户范围决定已回读到 #140/#147 正文。
