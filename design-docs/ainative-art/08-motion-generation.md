# 08-motion-generation 文字与视频生成动画

稳定需求 ID：ainative-art-08-motion-generation-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：文字动作生成、视频身体/手/脸流、时间基准、置信度、遮挡、接触与动作清理。

验收：文字动作及视频动作各一条真实链路；重定向前明确源 Profile；低置信区可修正；帧率、根运动、循环可验证。

前置：05-rigging, 06-skeleton-interop。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。

## 当前实现与验收边界（2026-11-07，待独立审查）

本项在隔离工作树实现 `tools/ainative/motion*.py` 与工作台 `motion.gd/motion_panel.gd`，目标 Windows / Godot 4.8。所有模型、独立 Python 环境、真实输入与输出留在被忽略的 `runtime/motion/`，不复用或更改 Comfy 环境。停止条件仍为本页完整验收及独立审查，不以接口实现或单测替代真实推理。

文字路线使用官方 [MDM](https://github.com/GuyTevet/motion-diffusion-model)（MIT，源码 `ef8edce6a53c6ab19e53b4d4dcf15bc0bc60a778`）HumanML3D 22 关节、50 步 checkpoint。权重来自官方 README 的 Google Drive `1cfadR1eZ116TIdXK7qDX1RugAerEiJXr`。使用真实 CLIP 文本编码、扩散采样和官方 `recover_from_ric`；仅排除 hml_vec 推理不调用的 SMPL 转换初始化，不修改神经网络或用规则动作替代推理。独立下载 CLIP 必须通过官方已知 SHA 后才能启动。模型代码 MIT 不代表任意训练数据授权自动转移。

视频路线采用 [MediaPipe Tasks](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker) 0.10.21 CPU，分别调用 pose/hand/face 官方 task 模型。每个解码帧保留原始 PTS 与提交模型的毫秒时间戳；各流保持独立坐标/单位、检测缺失、模型实际提供的 visibility/presence。手的 handedness 分数、脸 blendshape 系数不冒充关节点置信度；未暴露的置信度为 null。脸流最终角色绑定属于 #151。

已发生的真实验证：授权 Commons `dancer.webm` 经 166 帧推理，身体检出 113 帧、手检出 38 帧、脸检出 0 帧；`squat.webm` 213 帧身体全部检出、手检出 107 帧、脸检出 0 帧。两者保留缺失状态，未用零点冒充成功。原视频来源、许可、作者、SHA 见私有 `fixtures/*-source.json`。`dancer-v1.json` SHA `66097dd5fa6e5069a65055bc9711e49fbe575d2e5e96f509719590de3440fada`；`squat-v1.json` SHA `84d572aed6504d126fecd6dbfde901c52f9c9e135cda203eaa02b90e87b29ea2`。原始首次推理证据保留，后续合同升级不覆盖它们。

Godot 将源观测重建为显式 anatomical Profile（T 姿方向、首个完整观测的实测骨长），保存源 SHA 和处理策略后才调用 #147 `Interop.retarget`。位置模型不能确定轴向扭转；视频 hip-relative world landmarks 不能恢复绝对全局根运动，必须明确标记。工作台支持逐点修正、显式平滑、in-place、循环模式与新版本保存；手/脸不混入身体骨架。文本上下文有来源版本及实际消费说明；MDM 图片条件不支持，节点契约明确拒绝，不得宣称生效。

### 实际完成的链路与证据

- MDM/CLIP 全程 CPU 真实推理，4 秒请求得到 80 个 20 Hz 样本（首末时间 0..3950ms）；没有规则 prompt 映射或预录动画。`text-provider-final.json` SHA `cf453a549f2643fcb240a1ea5759f81e275ccfb289efb13be79f45ff83c22640` 为中间已验推理版本，后续 UI 按钮版本以回执为准。
- 清晰脸部授权视频 `frowning.webm` 得到 72/72 帧 face 检出，真实 blendshape 示例系数变化 0.448186..0.753339；手流缺失。`frowning-v1.json` SHA `2a94ab3227ea589276c7827f964d1848bae00dbe3b22074d4da17b35dfdc96ac`。蹲起视频虽然身体全检出，仍有 162 帧含 visibility < .5 的点，不能把 detected 等同于可靠观测。多人视频无持久人物身份保证。
- `ui-generated-squat-manny-receipt.json` 记录工作台实际 Estimate 按钮→异步 provider worker→模型三路估计→预览→低置信脚点修正→#147 Manny 161 骨重定向→24 fps/平滑/接触处理→不可变发布和重开。源 `ui-generated-squat.json` SHA `4b1fea4bb8efa71fa98b490355095e489d4babd99b0b8c3b5fb74a516c767f49`，保存 Animation SHA `0ffaf6421b8c9e5de2fe41c8a55048e2ff2036e2c942118cb2311aa5e82acecc`。修正是验收手工输入示例，不冒充真实动作 ground truth；第 2 帧脚点 31 原 visibility 0.497699，原坐标与置信度保留。
- 此次平滑最大改变量 0.023982m；水平根位移处理后为 0；显式左脚接触区间残差最大 0.020553m，未声称完美锁脚。姿态首尾最大角 seam 0.476796 rad，循环开关不会伪造无缝动作。`processing-validation.json` 对真实文字源验证 in-place、loop flag/真实 seam、平滑非零改变以及原文档未修改。
- 可见截图 `ui-generated-squat-manny.png`、`*-time0.png`、`*-preview.png` 展示实际动作面板、完整原生目标身体与两时刻。文字用原生 UE4 68 骨完整身体隔离机器人自身缺面质量；最终 `ui-generated-text-ue4-receipt.json` 记录实际 Generate 按钮 job `20430cf5480759583e1b75edb1f59c8f4fd600956bec3f453d894bb2abb137f0` 从 running 到 succeeded，再保存并重开 Animation（SHA `98e3c803b7950636acfca5316d14230c614c77710a1d1a0c8f6cc1a500ffc1de`），源 SHA 与上述 `cf453a...` 一致，源文档不变断言通过。对应三张图用于重新回读。原始机器人回放作为历史证据，不能宣称其网格生产质量。
- `Executor` 初次真实运行 `4820e511208b4fdba9c0246dd3fb8868` 已 succeeded；强化异步持久恢复后，最终运行 `ad84bada73d6407ca7cd793e0fd1ae43` 再次 succeeded，`executor-final-result.json` 保留动画 artifact 与 ContextBundle。实际 UI job receipt 也为最新协议验收。`motion_provider.factory` 与既有 NodeRegistry/Provider/Executor 复用，UI 不再知道 checkpoint 或模型参数布局；更换云 provider 通过受信任 factory 配置。
- 模型来源、代码提交、下载字节数、修改时间、SHA、许可依据统一留在私有 `provenance.json`；依赖完整锁定留 `dependencies-lock.txt`。公开安装与接口说明见 [MOTION.md](../../tools/ainative/MOTION.md)。MediaPipe 官方模型卡分别声明 Apache-2.0：[身体](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20BlazePose%20GHUM%203D.pdf)、[手](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20Hand%20Tracking%20%28Lite_Full%29%20with%20Fairness%20Oct%202021.pdf)、[脸](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20MediaPipe%20Face%20Mesh%20V2.pdf)。

恢复语义：原子 intent/manifest/receipt，独立 worker 排他锁，PID 与创建时间联合检查；模型结果已写但回执中断时可校验恢复，不重新推理。启动结果未知时明确 `reconciliation_required`，不永久假称 running、不盲目重放。CLI 等待 queued/running 至终态；本地不承诺强制取消正在执行的模型。

### 独立审查定向修正（保留原推理，不重跑模型）

独立审查发现旧最终 TSCN 实际缺失 AnimationPlayer：新节点未设 owner，原回读只检查 metadata，未检查动画。这是已确认的失败，旧 `ui-generated-*-receipt.json` 中的“重开”不足以证明动画保存，旧 TSCN 不作为交付。现为源 Skeleton/Player 和目标 Player 设置所有权，并使用独立场景副本在静止参考姿态下打包完整后代。新增回归强制重开恰好一个 Player、存在 generated 动画、轨道数量一致、所有轨道路径/骨名可解析、重开默认静止姿态，以及 0/中点两时刻所有全局骨变换与保存前相符。第二次保存须非零退出，不能仅用同 SHA 推定拒绝。

替代交付为 `ui-generated-text-ue4-review-fix.tscn`（SHA `4ee8cc2fb75b2fac5b18b6bfa309a8988e9d988ed7b6e276159cf1114b92fc0f`）与 `ui-generated-squat-manny-review-fix.tscn`（SHA `49ffed735fd52212d676a3cf8134cbadbffe7eaf5c168d74742e532d81228182`）；对应 `*-receipt-review-fix.json` 记录重开 204 / 483 轨，最大骨位置误差 2.74e-7 / 1.73e-7 米，重复发布退出码均为 1。这轮通过 Load 使用原按钮推理产生的不可变 JSON，`generation_button.triggered=false` 如实标明未再次推理。

两个 P2 同步修复：按源 Profile 严格校验 coordinate_system、源时钟枚举、HumanML3D 的米/+Y/20Hz 和非负有限时间戳；不兼容或缺失的有观测流坐标不静默默认。HumanML3D 无手脸观测的空流必须带 missing_reason，不推断不存在的坐标。原始根位移在平滑/in-place 前捕获，`processing-review-fix.json` 证明同一文字源 normal/smoothed 的 raw 均为 4.818692207m。

视频推理前后 SHA 均须与 invocation 期望值相同，worker 回收结果再核 provenance.input_sha256 与 invocation revision；源在推理期间变化时拒绝结果而不篡改来源。新增负向测试覆盖该变化及错误结果绑定。上述修正针对既有模型结果进行处理/回读，旧证据未覆盖。

必要检查：原有 58 项保持通过，新增合同/恢复故障检查后共 67 项通过。恢复测试覆盖 intent 后中断、结果后回执前中断、并发同 key 仅一次启动、终态不可变、进程身份复用拒绝；这些是明确故障注入测试，不计作模型推理验收。真实 Godot 脚本为 `motion_acceptance.gd`、`motion_validation.gd`、`motion_live_ui.gd`。发现并修复 HumanML3D 数组引用导致内存源首帧被参考姿态构造修改的问题，磁盘原始推理 JSON 未改；修复前 UI 版本保留为历史，不作为最终发布候选。
