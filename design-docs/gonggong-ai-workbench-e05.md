# E05 识别时间线的人工编辑

从原生选择发送动画播放器、Animation 或 AnimationLibrary 后，工作台按保存文件的 SHA-256 固定片段、轨道和关键帧。接续时比较同名轨道的出现序号、类型、属性路径和键时间。键的值和过渡均参与摘要。每个目标最多观察 128 条轨道与 2048 个键，超限会标明明细不可用。

Mac 验收在 AnimationTrackEdit 的 x 轨选择 0.5 秒关键帧，使用 AnimationTrackKeyEdit 检查器把 12 改为 18 后执行原生保存。新进程继续任务时，模型请求含本次保存者、修改轨道与键时间；未改的 y 轨摘要及三个键均相同。[设计条款](gonggong-ai-workbench-plan1.md#e05) · [逐轨回读](../data-collection/gonggong-ai-workbench-plan1-e05.json)
