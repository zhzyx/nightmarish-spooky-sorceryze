# 09-layering-equipment 上下半身分层与手持物

稳定需求 ID：ainative-art-09-layering-equipment-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：动画层、骨骼遮罩、Socket、主副手握点、手指姿态、IK、冲突优先级。

验收：跑步瞄准、单手挥剑、双手武器及换装组合可回放；主手/道具/副手无循环依赖；全身动作正确覆盖局部层。

前置：07-garments, 08-motion-generation。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。

## 本次本地实现与边界（2026-11-07）

授权沿父单 #140 issuecomment-6672872239，#150 intake-only 回读为 in-progress；责任者 kaiyunxue。仅 Windows 本机 Godot 4.8.beta.custom_build.ced0368bb；本子项新增独立分层核心、运行节点、配置面板和实际回放验收，按 root 追加授权在公共工作台新增三行分层面板入口，不提交/推送/关闭工单。停止条件是本范围实际实现、负向契约、保存重开及真实 UI 证据交给 root 独立核验。Quinn #202、面部生成、布料求解均不在此验收。

实现文件位于 `samples/ainative-workbench/`：`addons/ainative/layering.gd`（无环合成与 CCD）、`layering_player.gd`（原动画和动态层采样）、`layering_panel.gd`（真实配置/播放/换装/保存），以及 `layering_acceptance.gd`、`layering_live_ui.gd`。公共工作台已真实接入 `panel.initialize(host)`；UI 验收从该正常入口查找面板并滚动展示，不注入替代面板、不隐藏工作台。

### 数据与评估契约

- Skeleton revision 对骨名、父索引、完整 rest transform 做 float32 canonical SHA；换骨架/rest 后必须重新绑定配置。所有骨 mask 是明确骨名数组，不隐式扩展后代；full_body 必须无重复覆盖整个当前骨架（含辅助骨）。同 priority 按 id 排序；weight 0..1，override 插值；没有配置的骨保留原动画。
- 原动画每帧重采样→priority 升序动画层→主手 Socket 驱动物品→副手 CCD→手指姿态→final_body_pose→保留面部阶段→保留 cloth 阶段。full-body 缺省 pose 骨回退当前原动画完整 pose，从而覆盖低优先局部层。
- root/hips 只能由 base/full-body 层拥有；从真实骨架根与人体髋骨识别，不能删除配置 root_hips 绕过。head/neck 属 body；局部层只有明确 mask 才可写。#151 已协调只写面部 blendshape/眼睛，不回写 head/neck。
- equipment.priority 和 finger_priority 默认 15；任一副手求解链骨已被 priority >=15 的层拥有时抑制 IK，手指逐骨遵循同规则。高优先全身层因此同时覆盖局部层、IK 和手指。局部高优先手臂层也可以禁止 IK。
- 原动画驱动模式只挂接武器，不改副手。约束模式固定 `main_hand -> weapon -> off_hand`，拒绝任意其他依赖边及主手处于副手求解链后代的实际骨架循环。
- `weapon = main_hand_global * socket * inverse(main_grip)`；副手骨目标为 `weapon * off_grip * inverse(off_socket)`。Socket/握点均为有限非奇异 12 数值 Transform3D，单位米。示例使用真实掌心 middle_01 派生偏移，不将腕骨原点冒充掌心。CCD 只转动上臂/前臂，保留长度；手腕方向匹配目标，返回求解前后误差。不可达目标保留实际残差，不能把它当通过。
- fingers 是实际手骨后代指骨的局部 quaternion；非手指、手祖先、零 quaternion、未知骨拒绝。示例 30 指骨姿态明确作者构造，MDM 没有生成手指。
- `LayeringPlayer.pose_evaluated(Dictionary)` / `result` 输出 `schema=ainative.final_body_pose.v1`、skeleton_revision、timestamp_seconds、skeleton_local_metres、global_bone_poses（Interop.encode 数组）、local_bone_poses（运行时 Transform3D）、ownership、weapon_transform、ik 和 evaluation_order。#152 只读这个最终身体结果，不能反馈到身体或握点形成循环。
- 骨架/配置/clip 先验证，失败保留原姿态/武器/时间；UI 无效加载保留已有场景并清除旧预览授权。保存调用既有 interop_publish 原子 no-clobber 发布；重开保留原动画、动态层资源、Socket 和运行脚本。

### 真实本地验收结果

本机证据基准目录为本工作树 `runtime/layering/`（git ignored，绝不提交 UE 资产/模型/本机配置）。最终源场景 `ue4-v6.tscn`、核心回执 `ue4-v6.tscn.json`，UI 配置 `ui-final-v5.json`、装配 `ui-final-v5.tscn`、回执 `ui-final-v5-receipt.json`、四模式 1024×1024 图及完整 UI 图。

真实跑步 `run-v1.json` 由已有 #149 独立 MDM venv CPU 执行官方网络 50 步、seed 22、4 秒提示生成（80 个 20fps 源帧，回放 30fps），不是手工循环或旧动作查表。源 SHA `38bcf7ef5798e473686d6a0b049958e02facc4f35507e21413cc2a6631c90ed4`；prompt、官方源码/权重/CLIP/归一化数据/适配器 SHA 全在 provenance，真实日志 `run-inference.log`。沿用 #149 官方 MDM 来源与授权记录，不发布权重。UE4 native GLB SHA `14c0f1b3fcc4101bd04b791ff8d1e6e9a282b7d43506a62987f9424b4baa2446`，只本地验收、不发布专有资产。机器人无手指，未拿它作为手指通过证据。

核心 120 帧、14 项检查均通过：腿部实际旋转范围 0.90676 rad；主手掌心握点误差 0 m；副手解算前误差 0.063383 m、最大解算后误差 0.000483 m；30 指骨最终 quaternion 与配置误差 0 rad。实际验证全身全部骨 pose 覆盖、上下层优先级反转、全身抑制 IK/手指，以及循环、越界骨、骨架修订、局部 hips 拒绝。

真实 Godot OpenGL/NVIDIA UI 回放四模式各 60 帧：跑步双手握持、单手挥剑、原始动画驱动、高优先全身覆盖。单手上臂动态 clip 幅度 1.71667 rad；原始动画与全身覆盖均 0.58636 rad、无副手 IK。早期冻结躯干破坏髋部补偿的视觉问题已修正为保留真实躯干动画、只遮罩锁骨/手臂；最终放大图已检查。武器网格、瞄准/挥剑/手指姿态均明确作者功能夹具，不称 AI 生成。

换装使用 #148 已生成独立 shirt、armor（`garments/final-v3/config.json` 来源/SHA 校验），真实 UI shirt→armor→shirt 每次都重新加载原 UE4 基体，每次回放 30 帧，均 68 骨、未累加辅助骨；最大握点误差 0.000483 m，最后采样 0.000296 m。原子保存后重开 t=0.5s 误差 0.000298 m；重复目标拒绝、无效配置保留场景、源 SHA 不变。裙摆蹲下穿膝仍归 #152，本单未声称衣服布料已求解。

### 可复跑入口

在本工作树根运行（`$godot`、`$avatar`、`$motion`、`$newScene` 是本地路径；输出必须不存在）：

```powershell
& $godot --headless --path samples/ainative-workbench --script res://layering_acceptance.gd -- $avatar $motion $newScene
$env:AINATIVE_PYTHON = '<主 Python 可执行文件>'
& $godot --path samples/ainative-workbench --script res://layering_live_ui.gd -- '<新的 UI JSON>'
```

UI JSON 含 `scene`（上述新场景）、`base_avatar`（原生基体）、`family='ue4'`、`wardrobe`（#148 独立衣服配置）、`output`（不存在的输出前缀）；`stay_open=true` 可在验收后持续操作。面板可切换四模式、暂停、换装，并编辑完整 masks/priorities/socket/off_socket/grips/fingers JSON 后 Apply，保存新版本。验收场景构建夹具目前固定 UE4 骨名；核心基于骨名/绑定修订，不将此轮 UE4 证据扩大成 Manny/Mixamo/Quinn 的本单实际 UI 验收。

独立审查的实际 Skin/bind 测量已保留为 `layering_contract_tests.gd`：30 个指骨全部有蒙皮权重，2072 带指权重顶点，固定同一时间/手掌姿态开关 fingers 后最大实际顶点位移 0.09587946 m；不是只比较配置 quaternion。7 类非法输入加缺 mask、重复 mask、非有限时间均原子拒绝，所有失败保持前一 pose；高优先全身逐骨还原 base 并抑制 IK。运行 `--headless --script res://layering_contract_tests.gd -- <ue4-v6.tscn>`，最终日志 `runtime/layering/contract-final.log`，failures 为空。
