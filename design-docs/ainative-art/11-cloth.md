# 11-cloth 布料制作与运行

稳定需求 ID：ainative-art-11-cloth-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：仿真网格/渲染网格、绑定、固定权重、碰撞、LOD、缓存及实时/烘焙模式。

验收：披风和裙摆稳定播放；瞬移重置；体型变化使绑定/缓存失效；低质量回退；性能预算以目标机器实测确定。

前置：07-garments, 09-layering-equipment。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。

## 2026-11-07 本机首版候选

本单工单 [#152](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/152)，授权沿用 [#140 用户授权](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/140#issuecomment-6672872239)。intake-only 已回读 in-progress；前置 #148/PR219（`5a42d425b976057e9c531642b1659e5e01091c30`）、#150/PR228（`a61963195b3f75471be6e6a7f6ba05f6073db35d`）已交付。本工作树只实现本单、本地验证和移交 root；不自行 commit/push/关闭工单。Windows、当前自编译 Godot 4.8-beta `ced0368bb2dd2a5d2199c1f3ec46760a3406dead`，本机 i7-13700KF / RTX 4070 Ti；未声明其他机器或 Quinn 通过。

产物：`tools/ainative/cloth_prepare.py`、作者固定边校准 `cloth_pin_fit.py`、真实表面距离 `cloth_anchor_metrics.py`；工作台插件 `cloth_solver.gd`、`cloth_panel.gd`，正常 `workbench.gd` 的 ClothPanel hook；实际图形回放 `cloth_live_ui.gd`、完整合同 `cloth_acceptance.gd`、实际身体三角碰撞检查 `cloth_body_check.gd`，固定边导出/背侧检查 `cloth_anchor_check.gd` / `cloth_views.gd`。#150 的 `LayeringPlayer` 成功结果仅兼容增加 `input_timestamp_seconds`，由 root 明确授权，用于识别跨多个循环的大 seek；原有骨骼求值顺序不变。

### 来源和派生边界

原始资产位于主工作区被忽略的 `project/runtime/ainative-local`，本单派生/配置/证据位于本工作树被忽略的 `runtime/cloth`。下述本地路径均以对应工作树根为解析基准，不向 Git 提交专有原生角色、生成网格、原图或本机配置。保存的布料场景包含自洽的派生绑定和来源 SHA，不包含准备器的绝对源路径。

| 对象 | 不可变来源 | 派生处理 |
| --- | --- | --- |
| 披风 | `cloth-prep/cape-source-v4.glb`，SHA256 `7cff239ccd0f90c52934a6a4fb78718899587f627f0f0665f52f6e93f38e2502`，真实 image_to_mesh run `44e150f23dd4464ca015762b521f80a8`；图片与准备图的真实 SDTurbo 来源见同目录 `handoff152-source.json` | 110,843 顶点分为 104,845 和 5,998 两个组件；明确只选主连续片。原源层叠拓扑不能直接稳定渲染，作者按选定源面采样为 64×40 开放薄片，2,665 render 顶点；独立 16×12 proxy，221 sim 粒子。背面负 Z、肩部顶部 pin。 |
| 裙摆 | `garments/skirt-source-octree-v2.glb`，SHA256 `1a4575df118178159653a2d5fc6ea7b318f1a08ca8beaa01febefc16745a9a28`，完整生成 receipt 沿 #148 `final-v3/config.json` | 原源 485,382 顶点，主组件 484,512；只对 cloth 下摆作作者采样环面重拓扑，2,624 render 顶点，独立 24×10 proxy、264 sim 粒子。UE4 接缝 y=0.967506m。#148 原装配 `partitions.cloth` 之外的腰带/扣件三角、顶点和 skin 原样保留。 |

两者均非“AI 原网格已修复”，也不是把静态贴身蒙皮或预制摆动命名为模拟。源文件未覆盖。准备器输出原/保留组件数量、采样派生说明、参数网格对应误差 p50/p95/max（不是最近曲面 Hausdorff 误差）、原源 SHA 和准备绑定版本。未校准固定边前的披风采样对应误差 p50/p95/max 为 7.74/13.33/23.49mm；裙摆为 9.45/26.73/58.35mm，明确保留近似误差。披风最终 `cape-binding-v6.json` 进一步按实际肩背表面校准顶部，旧误差不是校准后整体误差；校准来源网格、输入绑定和实际肩背导出的 SHA 记录在 `pin_calibration`。只保留实际顶部渲染映射覆盖的四个固定点。初始聚类斑驳、悬空裙腰、披风固定边 52–59mm 离体的失败版本全部保留且排除；最终只采用 `cape-final-v5-*` 与 `skirt-final-v4-*`。

### 解算与编辑合同

独立实现世界坐标 XPBD 距离约束、重力与阻尼。每次接收 `ainative.final_body_pose.v1` 后才读取最终骨骼，绝不回写身体/手持装备。米制 rest 经 skeleton world transform 映射；所有非单位 world scale（包括非均匀 scale）明确拒绝，须先烘焙到米制资产。位置在世界坐标求解，缓存粒子在 skeleton 局部保存，重播时恢复到当前 world transform。

高质量按最大 1/120 秒子步、每子步 5 次约束；中档最大 1/60 秒、2 次约束。独立 proxy 的四点双线性权重及源面 rest offset 映射 render；再对实际 render 点做碰撞修正并重算法线、提交 ArrayMesh。身体/胸部/大腿/膝/小腿使用最终骨骼驱动的 capsule 代理，proxy 与 render 分别保留安全余量。最终算法版本 `xpbd-world-v3-weighted-render-contact`：render 接触修正按自由权重连续混合，完整固定边保留处方目标，不被近似 capsule 再推离；固定边及过渡带以真实身体三角检查，不能以“模拟点在 capsule 外”代替验收。原始/循环时间倒退、大于 0.1 秒步长、跨循环大 seek 或角色位移超过 0.5m 均重置位置和速度；不把大步长直接积分。

工作台可装配/重开真实披风或已分区裙摆、调质量/质量参数/顺应度/合法顶部固定权重、切实时/烘焙/回放、瞬移重置、保存新版本。`mass` 0.01..10、`compliance` 0..0.01、`pin_weight` 0.5..1；`pin_overrides` 是顶部已声明边界索引到 0..1 权重的对象，至少保留两个固定点，不允许把任意内部点伪称合法固定边界。`lod=0/1` 为求解质量档，`lod=2` 明示 rigid fallback / simulation disabled，不声称满精度布料。当前两档使用同一 render 派生层，不宣称原始百万三角实时模拟。

完整片段按 60Hz 固定输入烘焙；只有采样数覆盖整段且 key 匹配才允许回放。key 包含源 SHA、经过内容验证的绑定 revision、目标 Profile、DNA 全内容 revision、体型、solver 配置、输入场景 SHA、真实动画 tracks/keys 内容、层配置/动画名。动画资源修改或同名替换、形体/DNA/骨架/rest 更改禁止继续使用旧绑定/cache；绑定内容变化不能保留旧声明 revision 绕过校验。#151 合同使用 `character_dna`、`garment_fit_stale`；refit 从不可变基体及准备绑定重建。初始化失败保留旧几何但禁止继续求解；参数/配置失败不替换最后有效实例。烘焙有 generation 取消令牌，换装/重入/改参数不会让旧协程写入新实例。

保存先 stage，再调用既有 `interop_publish.py` 的原子 no-clobber 发布；重名拒绝。缓存和派生数据随 `.tscn` 保存，重开验证绑定/缓存结构、内容 hash 和目标骨架。正常工作台预览在成功替换时清除旧通用发布 token/confirmation，避免沿用无关批准状态。

### 验证与限制

当前真实基准：披风使用 #150 原生 UE4 `ue4-v6.tscn` 与真实生成动画；裙摆使用 #148 `final-v3/ue4-skirt-0.tscn` 的 squat。最终正常工作台两周期实时回放分别为 474 / 240 帧，完整 60Hz 烘焙分别为 237 / 120 帧；原子保存、明确拒绝重名、保存后重开对应 render 帧误差 0、非法参数/配置保留前实例均通过。早期完整合同的 LOD、瞬移、DNA 失效、非均匀 scale 负例保留版本说明；最终 v3 对变化部分重新做完整实际身体检查、正常 UI/cache 回放和独立差异检查，不宣称重新运行模型或每一轮旧测试。

最终 v3 `skirt-final-v4-body-intersections.json` 针对真实蒙皮身体的大腿/膝 rest band（knee_y−0.12 到 hip_y−0.10）：每帧 7,810 个实际身体三角，120 帧共 2,811,600 条边，对实际布料 render TriangleMesh BVH 相交检查，crossing_frames 为空、worst_crossing_edges=0。`cape-final-v5-body-intersections.json` 对实际肩背/上半身（rest 三角中心 y>1.2m）每帧 3,770 个三角、237 帧共 2,680,470 条边，同样零相交。它们是声明区域的全帧实际三角检查，不是全身体积无穿插认证。体型变更的 #148 `ue4-skirt-1` 同一膝区域也留有零相交补充记录，未改动该下方自由区域的证据可复用。root 已目视原腰带扣件保留、接缝贴合及蹲姿。

最终保存缓存同帧 119/60 秒的 `cape-final-v5-anchor-metrics.json`：四个模拟 pin 到处方目标最大误差 0；pin 到实际蒙皮肩背面 1.36–3.73mm；65 个 render 顶部点到实际面 1.41–4.33mm，依导入三角外法线的局部有向距离全正。背/侧视图同实例、同时间，仅改变相机及补光，不改几何。独立增量探针确认 pin_weight .999995→.99998 的最大 render 差仅 1.865μm、.99→.98 为 1.221mm，没有二值阈值导致的数厘米跳变；完整 pin 的 render 对处方目标误差约 0.242μm。

性能测量分 `solver_us` 与 `render_upload_us`（映射、render 碰撞修正、法线计算、ArrayMesh CPU 创建/上传提交），`total_us` 为两者之和；不把 CPU 提交耗时称为 GPU fence 耗时，也不把倒数当全应用帧率。停止并行推理后，最终正常工作台实测如下。预算只适用于本机当前单件派生资产；整角色、多角色/60FPS 预算留给 #154 实测。

| 最终证据 | solver p50 / p95 | render+上传 p50 / p95 | cloth 总计 p50 / p95 |
| --- | --- | --- | --- |
| `cape-final-v5-metrics.json`，474 帧 | 11.903 / 17.596ms | 12.882 / 13.313ms | 24.852 / 30.570ms |
| `skirt-final-v4-metrics.json`，240 帧 | 13.764 / 20.627ms | 12.969 / 13.928ms | 26.780 / 33.706ms |

独立审查已实际复核绑定篡改、失败初始化禁消费、动画同名替换/clip 变更、坏 cache、原始大 seek/倒退/正常 loop、原子发布/无本机路径、烘焙取消、13 个错误参数类型、旧算法 cache 失效及固定边连续性。临时探针来源由 root 记录，不以本单自写回执冒充独立审查。三个 Python 工具通过仓库固定版本 Ruff 0.17.1 check/format、Mypy 2.4.0、Codespell 2.4.2；未改共享推理环境。

首版限制：单件 cloth、指定校准代理、无布料自碰撞或两件布料互碰、无 GPU cloth、无全身连续碰撞认证。腰带继续原装备蒙皮；rigid fallback 是公开降级，不是模拟。没有复制 Unreal 专有实现。算法只参考作者论文 [XPBD (Macklin, Müller, Chentanez, 2016)](https://matthias-research.github.io/pages/publications/XPBD.pdf) 的约束公式，代码独立编写；论文版权归作者，本文仅链接、不分发论文或第三方实现。

本节是候选实现与实测范围记录，独立审查/精确候选门禁和 root 汇总业务验收完成前不得将本工单标为完成。
