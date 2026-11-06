# 05-rigging 人物标准化、自动绑骨与蒙皮

稳定需求 ID：ainative-art-05-rigging-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：标准人物路线和自由 Mesh 路线、参考姿态、自动骨架、蒙皮、ROM 验证与人工修正入口。

验收：一个生成角色通过抬臂/深蹲/转身动作检查；绑定姿势、单位和权重有效；坏拓扑可诊断；Godot 内播放。

前置：04-generators。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。

## #146 实现边界与入口

本次产物为 `samples/ainative-workbench/addons/ainative/rigging.gd`、工作台人物面板、实际 Godot 验收脚本和 `tools/ainative/rigging_publish.py`。目标平台是当前 Windows Godot 4.8 定制编辑器；不编译引擎、不下载模型、不引入第三方 Python 依赖。使用独立实现的解剖模板、截面深度拟合和骨段距离权重，不称为通用 AI 自动绑骨。停止条件是实际生成角色的可追溯衍生版本经 ROM、Skin/rest/权重和发布重载检查，并完成独立验收；这里的开发测试结果本身不替代 root 的业务验收或 Git 交付。

生成 Mesh 的工作台预览下方提供人物操作面板：选择标准人物或自由 Mesh，设置米制目标身高、显式源 Y 裁底阈值和可选重复/退化面清理，再点 Fit / preview cleanup。每次清理都重新显示模型及保留/移除面数、开放边和非流形边；原 GLB 永不覆盖。清理仅删除选定面，不自动补洞，不声称修复所有拓扑。边诊断按坐标量化至 1e-6 的几何边统计，因此不同于仅按原索引的连通组件统计。

标准路线限定：Y-up、+Z 朝前、近似直立对称、双臂展开的 T 参考姿态、双腿分离、头和四肢有独立可见区域。程序检查宽高比、头/左右臂/左右腿区域占据数、左右臂占据大致对称、腿关键点高低顺序及 X 对齐；这些必要条件不是人体语义分类器，使用者仍须检查预览并确认。初始 18 骨为 17 个解剖骨加独立 root；深度通过对应几何截面中位数拟合，身高归一为米，底部归零、X/Z 居中。非标准人体、未知物体不能因能加载 Mesh 就被当作绑骨成功。

自由路线需要全部 17 个解剖关键点，root 可选覆盖。先 Fit 得到待标记预览，再点 Load fitted joint markers 将实际拟合点载入修正区；坐标使用归一化后的米制坐标。修正 JSON 的 `reference_pose: "marked"` 表示人工标注源真实姿态，可用于略下垂手臂的 A 姿角色；不假称原模型已变成 T 姿。未完整标记或未检查确认时，允许诊断与预览，拒绝角色发布。黄色线段显示当前骨架，可播放 raise_arms、squat、turn 或恢复 Rest。

## 修正、版本与发布

修正区的 `joints` 按骨名给出 `[x,y,z]` 米制关键点；`weights` 按压缩后的逐 surface 顶点序号给出至多四个 `骨索引: 权重`，拒绝非法索引、负数、非有限数和全零权重。骨索引顺序见脚本 NAMES；Load fitted joint markers 会附带 `weights_geometry`。权重身份绑定源 SHA256、裁切、清理、身高、朝向和算法版本，任一改变均不能静默套用旧顶点修正。失败的 Fit 不提交新参数；重新载入骨点也不能为旧权重换绑。改变清理后必须清空权重、重新拟合并重新标记。

面板 Save new character version 先编码到私有 staging，再经既有 `publish_new` 的同目录临时文件及原子独占 hard-link 发布，拒绝覆盖任何已有目标。发布副本重置为参考姿态，保留三段真实 AnimationPlayer 动画；当前预览不受影响。Reopen version + corrections 重载 `.tscn` 中的 Skeleton3D、Skin、动画及修正参数，核对本机已知源 SHA256 后继续修改；修改需另存新文件名。本机源路径仅保存在 user 数据目录的配置中，不进入便携角色元数据。派生预览会清除生成器原预览令牌，不能绕过角色审查走普通生成物发布按钮。

角色携带 v1 `ainative_manifest`：source mesh、skeleton_profile、avatar_profile、character 均有版本引用，来源绑定原文件 SHA256，character 仅声明 semantic_mapped。骨骼局部 rest 轴为 identity，Y-up/+Z 朝前；尚非 SkeletonProfileHumanoid，也不宣称已兼容 UE/Mixamo，留待 #147 转换。Skin 使用真实逆 global rest，4 权重归一；足底使用 foot 刚性权重并向小腿平滑过渡，人工权重覆盖优先。深蹲使用双腿平面两段 IK、hips 下移和足踝角度补偿，当前约束要求髋膝踝近似处于各自 sagittal 平面，不支持任意怪物、额外肢体、手指或脸部骨。

## 开发验证记录

Intake：`#146 / ainative-art-05-rigging-20261106` 回读通过；责任人为 kaiyunxue，授权来源沿用父任务的 `#140` 授权评论。当前实现者不 commit/push/关单，root 负责证据归档、最终独立复核与 Git 交付。

- Python `-m unittest discover -s tools/ainative -p 'test_*.py'`：55 项通过，包含原有 53 项和新发布 no-clobber/非法编码检查。
- 真实 Godot 工作台启动通过。`--headless --path samples/ainative-workbench --script rigging_acceptance.gd -- source.glb new.tscn params.json` 实测真实机器人原始 33635 点；源 SHA256 为 `cb2898e0bcb5b07c311a7da776a0b882e14fcc53cc867b05058a4d86f7ed0ae6`。
- root 提供的实际 `robot-marked.json` 使用 `free/marked`、人工关节与显式 `crop_below_y=-0.94`，目标身高 1.8m。衍生保留 22897 点，删除 38689 面；开放边 217、非流形边 8331，仍保留警告。这是裁底衍生物，并非已修复的流形人体。
- 最终开发重载检查：18 骨；静止几何最大误差 0.000082493m（Godot 压缩权重的量化误差，允差 0.0002m）；逐点骨索引有效、权重有限非负，和误差 < 0.0001。
- 重载后实际 CPU Skin 变形的最大顶点移动：抬臂 0.482693m、深蹲 0.337760m、转身 0.642121m。41 帧深蹲检查最大踝漂 8.57e-8m、实际足底顶点漂移 1.085e-7m。检测的不仅是动画存在或骨头移动。
- 负向检查覆盖源 hash 不符、负身高、非法骨权重、未标记自由 Mesh 保持待修正。验收脚本显式收集失败并返回非零退出码。
- 过程中曾发现脚底穿地约 8cm，原因是仅约束踝位置仍混入小腿权重；已修复足底分配并增加真实脚底顶点接触检查。开发默认模板和最终人工标注机器人结果分别记录，不能混为默认算法已自动理解该角色。

以上数值来自当前本地开发验收，最终业务截图、发布 no-clobber 实际回执、独立复核及目标 main 版本由 root 的公共证据记录承接。实际源模型与体积较大的 `.tscn` 留在运行目录，不纳入源码夹具，不用合成立方体代替真实角色验收。
