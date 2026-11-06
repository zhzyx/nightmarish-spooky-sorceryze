<!-- gonggong-request:ainative-art-pipeline-20261106 -->
<!-- gonggong-host-git:kaiyunxue -->

# AINative 美术与人物工作流实施方案

版本：2026-11-06 v1。路径基准：仓库根。用户授权：本聊天“把上述任务拆分一下然后落地吧”。

## 边界与交付

先完成通用管线，再以领域能力包接入人物、装备、动画、布料和毛发。当前首个实现单元为 01-contracts：可执行资产契约验证器、样例及负向测试。Windows / Python 3.11+ 验证该单元；引擎集成在后续子项使用 Godot 原生 Resource/编辑器能力。本文不将任务建单或契约验证当成整套功能已实现。

生成 Provider 的选择与真实服务凭据在 04/08 单元验证；未提供时保留外部依赖，不虚构生成结果。所有实现默认编辑器内生产、运行时消费发布资产；运行时在线生成另作扩展。标准人体与自由 Mesh 两路并存，服装不承诺跨任意体型无损复用。

## 架构约定

- 管线内核：类型化资产、上下文、任务执行、Provider、缓存、版本、插件注册、发布适配器。
- 领域包：Character / Rig / Animation / Garment / Face / Cloth / Hair；可以注册资产、节点、验证器与预览器。
- 引擎运行时：装配、动画求值、约束、形变、物理、LOD；不直接依赖生成 Provider。
- Context 必须区分文字、图片等参考的角色（风格/身份/姿态/结构）、作用域、强弱约束与来源；不能把全部上游内容无差别拼入提示词。
- Artifact 使用不可变版本引用；显式记录坐标、单位、参考姿态、拓扑身份与来源。改变体型/拓扑/绑定姿势需使服装拟合、毛发绑定和模拟缓存失效。
- 衣服可无目标先生成 draft；绑定或宣称兼容时必须有实际角色或 AvatarProfile。AvatarProfile 描述体型和表面，SkeletonProfile 描述骨骼，两者不可互换。
- 装备允许 shared bones + accessory bones；extra bones 不自动追加至所有角色。刚性胸甲、蒙皮皮带、布料裙摆可属于同一装备。
- 兼容等级分为 semantic_mapped、animation_retargeted、target_bound、roundtrip_verified。名字相同只证明映射候选；目标骨架层级、bind/rest pose、单位、骨轴、辅助骨行为、蒙皮和目标工具回读分别验收。
- UE4、UE5 Manny/Quinn、MetaHuman Body 与 Mixamo 分版本 Profile；辅助 IK 骨不必有蒙皮权重；扭转与修正骨需要驱动规则。Mixamo 命名空间非破坏映射，独立 Root 可选。
- 动画先在源/目标明确的空间完成重定向，再混合目标空间动画；装备/接触 IK 在主体混合后。脸部声明头颈写入权；布料消费最终身体碰撞形状。不能把所有流固定为混合后统一重定向。
- UE 仅作架构参考，不复制其 Engine 代码；独立开放组件与资产在引入时逐项核对许可证。此前讨论的精确版本与开源可用性尚未在此仓库验证，不作为已具备能力。

## 父级验收

13-integration 负责集成验收；各子项负责自己的可独立验收行为。六项原始要求分别映射：上下身→09，手持→09，衣服盔甲→07，脸部→10，布料→11，毛发→12。多模态任意阶段上下文→01/03/04/08，捏人→10，独立装备→07，UE/Mixamo→06。Motion Matching 与 ML Deformer 仅为未来增强，不是用户要求的首轮完成条件。

## 任务清单

每项主责：当前执行者 Codex（GitHub kaiyunxue）；后续交接需写明实际接收者。各项交付目标为 main，未验收保持开放。

| ID | 可独立交付单元 | 依赖 |
| --- | --- | --- |
| 01-contracts | [资产、上下文与扩展契约](ainative-art/01-contracts.md) | 无 |
| 02-executor | [工作流执行与持久任务](ainative-art/02-executor.md) | 01-contracts |
| 03-editor | [引擎内工作流编辑与发布](ainative-art/03-editor.md) | 01-contracts, 02-executor |
| 04-generators | [图像与 Mesh 生成节点](ainative-art/04-generators.md) | 02-executor, 03-editor |
| 05-rigging | [人物标准化、自动绑骨与蒙皮](ainative-art/05-rigging.md) | 04-generators |
| 06-skeleton-interop | [UE 与 Mixamo 骨骼兼容](ainative-art/06-skeleton-interop.md) | 05-rigging |
| 07-garments | [独立衣服盔甲生成、拟合与装配](ainative-art/07-garments.md) | 05-rigging, 06-skeleton-interop |
| 08-motion-generation | [文字与视频生成动画](ainative-art/08-motion-generation.md) | 05-rigging, 06-skeleton-interop |
| 09-layering-equipment | [上下半身分层与手持物](ainative-art/09-layering-equipment.md) | 07-garments, 08-motion-generation |
| 10-customization-face | [捏人捏脸与面部叠加](ainative-art/10-customization-face.md) | 05-rigging, 07-garments, 08-motion-generation |
| 11-cloth | [布料制作与运行](ainative-art/11-cloth.md) | 07-garments, 09-layering-equipment |
| 12-hair | [毛发生成、绑定与分级表现](ainative-art/12-hair.md) | 10-customization-face |
| 13-integration | [端到端角色工作台验收](ainative-art/13-integration.md) | 03-editor, 04-generators, 06-skeleton-interop, 07-garments, 08-motion-generation, 09-layering-equipment, 10-customization-face, 11-cloth, 12-hair |

## 检查及停止条件

01 运行标准库 unittest、样例检查和 git diff --check；其他子项按各自验收执行。门禁、远端 PR/CI/main 回读按仓库约定。不存在 Provider 或目标工具时仅挂起相关验收，不能报完整系统完成。工单映射和实际回执追加在本文，不擅自关闭父单。

## 实际工单与首批交付记录

父工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/140 。创建并回读日期：2026-11-06（Asia/Shanghai）。

- 01-contracts：[Issue #142](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/142)。
- 02-executor：[Issue #143](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/143)。
- 03-editor：[Issue #144](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/144)。
- 04-generators：[Issue #145](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/145)。
- 05-rigging：[Issue #146](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/146)。
- 06-skeleton-interop：[Issue #147](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/147)。
- 07-garments：[Issue #148](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/148)。
- 08-motion-generation：[Issue #149](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/149)。
- 09-layering-equipment：[Issue #150](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/150)。
- 10-customization-face：[Issue #151](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/151)。
- 11-cloth：[Issue #152](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/152)。
- 12-hair：[Issue #153](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/153)。
- 13-integration：[Issue #154](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/154)。

本候选主关联 #142；总设计及其他子项文档作为接口实施的需求溯源随首批提交，其他子项实现不计入本候选。01 首批交付 tools/ainative/ 的 Manifest 验证器、样例与测试；节点注册、Provider 和发布可执行接口尚待实现，因此 #142 与父单保持开放。当前没有实际模型调用、UE/Mixamo 真实夹具、引擎 UI 或物理求解器交付。

## Codex 接续执行决定（2026-11-06）

用户选择“由当前 Codex 按依赖执行，大千展示进度”。执行责任为当前 Codex 会话；大千计划、节点状态和 GitHub 工单显示实际进度，独立常驻生产宿主不作为前置。已真实登记并回读全部 GitHub blocked_by 关系及司南 gonggong-depends-on 来源标记。#142 剩余扩展契约先验收，然后依次解锁 #143、#144；有独立且已满足前置的子项才并行。仅在真实需要凭据或用户决定时通知，不因部分 PR 合入停止用户目标。

本次 #142 接续候选增加版本化 NodeRegistry、Provider 描述/调用/状态/输出验证及 PublishAdapter 编码与新文件原子发布契约。真实模型调用、异步持久执行器和 Godot 编辑器分别由后续子项验收。基础契约使用合成夹具验证，不将其作为真实 UE/Mixamo 适配证明。发布回读及关单以 #142 时间线为准。

## 已核实的依赖推进

| 子项 | 实际验收与交付 | 后续动作 |
| --- | --- | --- |
| #142 | PR #161；main 接收 fe4a8d3a80bde5413e330e9139d514103e225d81；22 项测试及独立复核通过；GitHub CLOSED / COMPLETED 已回读 | 解锁 #143 |
| #143 | PR #162；main 接收 6e325eb90d8beda9fe84b713451b7aa30c2df623；37 项测试通过，独立审查通过；GitHub CLOSED / COMPLETED 已回读；大千保存完成回执 | 解锁 #144 |
| #144 | PR #163；main 接收 b9433dcabe69be1a8850a42a9fe8b9234829b867；39 项 Python 测试、真实 Godot 回放和独立审查通过；GitHub CLOSED / COMPLETED 已回读 | 解锁 #145 |
| #145 | PR #192；main 接收 f537f112ac3e8c8ed62b748f5f6fd4cf790d0867；53 项测试、四种实际生成、Godot 预览发布重载及上下文 Run 通过；独立审查、GitHub CLOSED / COMPLETED 与大千 completed 已回读 | 解锁 #146；原始 Mesh 质量限制保留 |
| #146 | PR #198；main 接收 3003153c21cf42e865d39f06abb4115421046527；55 项测试、真实角色 18 骨蒙皮/三段 ROM/足底接触及工作台发布重开通过；GitHub CLOSED / COMPLETED 与大千 completed 已回读 | 解锁 #147；保留原始拓扑质量限制 |
| #147 | PR #203；main 接收 4934dcd836493366c89a93078596d53f41d2c6be；58 项测试、真实三套骨架/根运动/手指/接触、完整 UI 和 UE 回读通过；GitHub CLOSED / COMPLETED 与大千 completed 已回读 | 首版 UE4/Manny/Mixamo；Quinn 按范围决定留在 #202；解锁 #148/#149 |
| #148 | 三件真实独立生成、两骨架×两体型12例装配及14次UI回放；65测试和独立审查通过；本地验收完成，精确候选交付推进中 | 服装仍有表面层纹；裙摆蹲姿碰撞归#152与#154后续验收，不宣称布料完成 |
| #149 | 本机CPU文字/视频真实推理、UE4/Manny回放；保存丢动画等审查问题已修复，重开204/483轨通过；70测试与独立复核通过，待顺序整合交付 | 原始推理数据保留；旧缺动画场景撤销；手/脸独立流和能力限制明确记录 |

表格最后核实：2026-11-07。本地计划状态、工作者完成与业务验收分开记录；#148/#149 本地验收不表示远端交付；最终以PR/main及工单回读为准。

第一版部署决定：生成模型独立于 Godot 进程，通过 Provider/HTTP 任务接口接入。本机地址、凭据和存储路径保存在机器配置；图保存语义、资产版本与参数。模型权重和推理环境放本机忽略目录。以后迁移同一后端只更换部署配置；换模型仍须重新验证生成效果与后续资产兼容。

## 首版范围决定：Quinn 后续验收（2026-11-07）

用户明确决定：“首版先验收 UE4、Manny、Mixamo；Quinn 保留为明确待验收项”。因此 #147 和 #154 的首版骨架兼容验收范围为这三套，其他验收保持不变。原 Quinn 完整身体要求由首版之外的 [#202](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/202) 与 [后续设计](ainative-art/06-quinn-validation-followup.md) 保留，当前未实现验证，不计入首版完成数，不阻塞原首版依赖。#140/#147 远端正文已同步并回读这一范围决定；不是把 Manny 或 XR 手部当作 Quinn 通过。
