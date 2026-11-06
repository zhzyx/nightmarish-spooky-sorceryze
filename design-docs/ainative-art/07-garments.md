# 07-garments 独立衣服盔甲生成、拟合与装配

稳定需求 ID：ainative-art-07-garments-20261106。工单：[#148](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/148)。授权：[父需求确认](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/140#issuecomment-6672872239)。主责：Codex / kaiyunxue。父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。前置 #146 / #147 已验收；本轮 intake-only 已通过，目标 main，由 root 独立审查和整合，工作者不自行提交。

## 本轮实现与边界

Windows / 本仓库 Godot 4.8 beta / 本机 ComfyUI 上，独立生成上衣、胸甲、带裙摆装备；服装始终为独立源版本，再针对不可变 AvatarProfile 派生装配。完整验收包括三件真实生成、两个非等比例体型、越界失败、源不覆盖、UE4/Mixamo 实际骨架和 Godot 回放。布料物理解算属于后续 **#152**；当前只实现 cloth 分区、固定区和附属骨绑定。轴向 cage 是审阅式拟合，不声称自动碰撞解决或生产质量服装拓扑。

- `tools/ainative/garment_generate.py` 经现有 Executor/ComfyProvider 实际推理，保存 run、prompt、模型/工作流/输入及输出 SHA 回执；同目录临时文件+独占硬链接发布，已有版本不覆盖。超时保留run，`--run` 可继续并为字节一致的已发布源补缺失回执。
- `garment_prepare.py` 对真实 AI 图做显式颜色选择、裁剪、白底留白，保留原图、二值mask和派生SHA；输入/三输出解析后互异，先读取源快照，每文件原子独占发布，不生成几何。
- `garments.gd` 同一快照校验源SHA与自包含GLB再导入；拒绝外部URI、篡改骨名/父级/local/global rest、派生装配再次作源。Garment metadata 保留源版本、生成回执hash、AvatarProfile revision、目标来源、体型、分区和派生revision。
- 胸/腰/髋/厚度分别在0.8–1.2范围变化，身高不变；同形变作用于派生身体与衣服，越界明确失败。胸甲单胸骨刚性绑定，上衣共享语义骨平滑权重，裙摆有附属骨和cloth/pin分区。扩展记录基础Profile、完整新增骨定义及组合revision；换装重新读取基础Avatar，无骨/衣服累积。
- 工作台 Garments 入口提供配置读取、目标/衣服/体型选择、拟合换装、动画、保存；面板就地显示共享预览。完整校验配置成功后才提交UI状态。保存使用既有原子发布器，重开核对Skin/binds/weights/manifest。派生法线按Godot顺时针绕序重建并以实际源法线方向回归。

文字条件实际进入 SD-Turbo diffusion，图片条件为 img2img 初始latent或Hunyuan vision。当前provider只支持一个图片约束；source与image context同时传入明确拒绝，不冒称多图融合。最终衣服图由独立服装提示生成，身体从未拼入衣服生成。生成阶段尺寸文字是authoring上下文；不可变Profile绑定来源在实际fit阶段固定。

## 最终候选与真实证据

私有证据根为本机既有运行时 `garments/`，大资产、数据库、配置和截图不进入Git。最终配置为 **`final-v3/config.json`**；三源均为未经程序造型/孔洞修补的真实 Hunyuan 输出：

| 独立源 | SHA256 | seed |
|---|---|---|
| shirt-source-octree-v7.glb | 0061d01632e4e6d0e4bebd7a7ccd4c0432649b2f14d6d94d0f9e793f106c3048 | 1481 |
| armor-source-octree-v2.glb | 29d343b254bda480ffdfc437f13ad27f03c1576d1f319ffa79d0e5c90ed65b60 | 1482 |
| skirt-source-octree-v2.glb | 1a4575df118178159653a2d5fc6ea7b318f1a08ca8beaa01febefc16745a9a28 | 1483 |

服装入口默认采用本轮实际改善的 **512 latent / 20 steps / threshold 0.5 / octree 256 / surface net**；共享ComfyProvider全局默认保持兼容，诊断参数可显式覆盖。非turbo MINI 的[准确官方配置](https://huggingface.co/tencent/Hunyuan3D-2mini/blob/main/hunyuan3d-dit-v2-mini/config.yaml)是512 latent；Comfy通用节点3072并非本模型的正确默认。当前Comfy把VAE logit映射为clamp((logits+1)/2)，0.5对应logit零等值面。

SD-Turbo权重SHA：`3f067a1b943cf162f2b8f8588f6cf5824bd5b4c7d1d88d87164b9ca123616549`；Hunyuan mini权重SHA：`3cc66f3bea33e4062b7dbc875ffe1d70c4888914aec3e91b60f94e9bd01b522b`；ComfyUI revision：`63e5bf594339f676b4b15e072529873e3448409e`。每源同名 `.receipt.json` 保存实际模型、工作流、输入及远端作业来源。

最终衣服cage明确记录在spec.target_box中：上衣 `[-.24,.97,-.22,.48,.60,.44]`、胸甲 `[-.26,1.03,-.24,.52,.54,.48]`、裙摆 `[-.30,.58,-.25,.60,.52,.50]`（米；位置xyz+尺寸xyz）。它们是针对这三件源与本轮目标的审阅校准，不是通用拟合承诺。上衣开放侧面关闭整段躯干遮挡，裙摆不遮挡躯干；胸甲明确采用审阅式躯干遮挡。

- `final-v3/acceptance.json`：三件×真实 #147 UE4/Mixamo 目标×两体型，共12例。第二体型胸1.15、腰0.9、髋1.1、厚度1.15；验证真实顶点差异、蒙皮动作位移、完整分区、UNORM16权重量化界、骨扩展、源SHA不变、越界/覆盖拒绝。保存后重开比较完整Skin绑定、顶点/索引/骨/权重、规范manifest revision和同动作形变。还拒绝只改父级的骨架及容器SHA正确但依赖外部buffer的GLB。
- `final-v3/fit-*-*.png/json`：12种实际UI装配的正/侧/背和动画图；`swap-2-1`、`swap-1-2`为裙→甲→裙的实际UI回放，检查独立实例与骨数无累积。`workbench.png` 是1280×800完整操作区与预览；对应上衣UI回执包含真实Save、reopen、no-clobber以及非法wardrobe不破坏旧状态。
- 独立三视图：上衣 `shirt-octree-preview-v7-*`，甲与裙 `final-v1/{armor,skirt}-source-*`；这些源字节未再修改。`final-v3/native-shirt-*` 另用原生UE4完整身体经Interop导入/提取/保存后的对照，开放背心侧面保留身体。`final-v2/avatar-base-comparison-*` 保留原生成robot未遮挡对照。

所有验收程序的scope仍为 **contract-only**，最终新源 `visual_status=pending_manual_review`，由root结合三视图/动画独立业务复核，不由测试自动宣称视觉通过。上衣仍有层状表面纹理；裙摆局部有薄片/细孔，原机器人无手指、手臂等本身有孔洞/非流形。clearance使用实际三角BVH的约6000身体边交点采样及约512衣服顶点双向径向表面距离；非闭合身体与抽样方法不能证明无穿插，完整统计保留私有回执，公开摘要只保留数量、指标及manifest hash。

## 检查与诊断沿革

Python **65项通过**（原58，加mesh参数2、原子生成恢复2、prepare源/sidecar不覆盖2、服装preset1），`git diff --check`通过。Godot额外实际验证源法线方向、骨层级篡改拒绝、GLB外部依赖拒绝、保存重开同动作、UI非法配置状态保留、原子不覆盖发布。测试结果不替代模型或外部资产质量验收。

旧失败全部保留，不覆盖、不回溯标成功：SD-Turbo多轮图带入人台/裤装或裁切；上衣采用shirt-image-v2的蓝色区域且y<477去裤，裙用棕色区域23≤y<477去腿，胸甲加白底padding，原图及mask/prepare回执可追溯。128octree的三源严重条纹缺面；basic、双面诊断、3072latent及threshold0未修好。仅同512/.5把octree128提高256后显著恢复薄壳，这由真实新输出确认。CPU大孔修补未采用，诊断脚本和偏差记录仅保留私有runtime，不发布未验收修补能力。assembly-v1的权重量化阈值失败、v5原始float64字典比较失败分别修正为真实UNORM16误差界和既有Profile float32规范revision；历史错误回执保留。final-v1/v2用于遮挡与法线诊断，当前候选只认final-v3。

## 复核入口

```text
python tools/ainative/garment_generate.py --source prepared.png --output NEW-source.glb --seed 1481
godot --headless --path samples/ainative-workbench --script garments_acceptance.gd -- NEW-config.json
godot --path samples/ainative-workbench --script garments_live_ui.gd -- NEW-ui-config.json
```

生成使用既有 `AINATIVE_COMFY_CONFIG`。验收配置含targets（实际角色path/family/version/authority）、garments（独立GLB path及spec id/version/kind/source_sha256/target_box）、新output_dir/receipt。UI配置含wardrobe路径、目标/衣服索引、shape及新screenshot_prefix/receipt，可选source_only、swap_to、save_path、workbench_screenshot；保存使用 `AINATIVE_PYTHON`。所有输出必须选新版本。模型/大资产仅私有runtime；代码不包含本机路径、账号或权重。

## 主任务业务复核

2026-11-07，root独立查看真实三源、最终UE4/Mixamo装配/体型/动作代表视图、原生UE4开放背心对照及完整工作台，确认本单首版独立生成与装配范围通过。公共证据为 `data-collection/ainative-garments-validation.json`；测试程序的contract-only与pending_manual_review字段保留原义，另有root视觉复核回执。裙摆蹲姿仍可见膝部穿插，本单没有布料求解器；#152必须验证身体碰撞与裙摆稳定性，#154必须复播该集成场景，不能把本单装配通过称为布料通过。源码独立审查已通过，随后沿精确候选CI和main回读交付。
