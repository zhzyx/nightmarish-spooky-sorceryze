<!-- gonggong-request:engine-next-visual-runtime-m4-1-20261115 -->

# Engine Next M4.1 — D3D12 RHI 与 FrameGraph

## 当前授权与范围

子 Issue https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1327，父 Issue https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1323，原生父子关系已创建并回读。用户于 2026-11-15 在 M4.0 设计 PR #1326 合入后明确“请落地”，确认设计并授权按阶段实现。当前子单从 main `49e0bd2444be533847e3c3ee798d01185c15b99a` 开始，执行责任为当前 Codex 会话。

本阶段交付原生 Windows 窗口与输入、独立 D3D12 device/queue/fence/swapchain、GPU buffer/texture/descriptor 生命周期、固定网格及基础 shader、显式 FrameGraph、时间戳/资源诊断、实际 GPU validation 与干净目录运行。实现遵循项目 C++17、无异常、PascalCase、类型前缀、明确 RAII 所有权及线程边界。详细设计沿用 `design-docs/engine-next-visual-runtime-m4-20261115.md`。

## 验收

- 原生窗口、resize/minimize/restore/退出、键鼠输入有实际回执。
- 自有 D3D12 管线绘制固定 mesh，包含深度、离屏颜色及呈现，图声明真实驱动资源状态转换。
- FrameGraph 检查依赖、循环、读前写、UAV/transition、持久/暂态生命周期及跨队列顺序；回归测试覆盖错误输入。
- 记录设备能力、显存、CPU/GPU 时间、pass/barrier/resource，每帧可导出。
- GPU Validation 无 error；固定场景在干净目录可运行，截图/视频/PIX或RenderDoc捕获按实际生成留证。
- 真实链接、符号、DLL/发布包与无 Godot 契约通过，M2/M3 原入口回归通过。
- 独立审查、正式门禁、精确 CI、main 回读；通过后关闭本子单。父单其余阶段持续推进。

## 执行与验证

当前实现已通过首轮 Windows/MSVC 编译、13 项 FrameGraph 测试和 RTX 4070 Ti 的120帧 GPU validation（含2次resize）。最终候选仍需独立审查、捕获与门禁。每次实际测试绑定候选、设备与输入。当前显示器为1440p，原生4K输出验收仍需实际模式确认。UE A–F 基准采集作为父级未完成项继续推进。

## 当前实际交付候选

- 独立 Win32 窗口、raw input、失焦释放、resize/minimize/restore、RAII 关闭。
- D3D12 硬件 device、graphics/compute/copy queue、fence、RTV/DSV/SRV/UAV、固定 indexed cube、深度和颜色目标、三帧资源退休。
- FrameGraph 自动 transition/UAV、跨队列 Common 交接和等待计划，资源级访问串行化，子资源状态、有界 DAG 与失败事务性。物理资源分别分配。
- 离线 DXC shader、独立发布包、GPU timing、完整图资源/依赖/状态记录、65536 帧有界计时环、DRED 故障信息读取。
- 实机 240 帧 GPU validation 无错误、两次 resize，干净发布目录120帧与PATH启动12帧通过。
- 66000帧计时环回绕通过，保留最后65536帧并逐帧关联GPU结果。该短时高帧率实验只证明计时环回绕。
- 实际 RenderDoc D3D12 捕获回放、8秒240帧原生画面视频通过。绑定当前EXE摘要 `3c760000cfc9a1bf3d9a38bff79bb110a7f0c0e9bfe67cc30e18972203279c28`。
- M2/M3完整独立运行时回归、资产/AI/双客户端/重连/drain/干净目录和runtime package验证通过。VS18暴露原有TestBlobValidator填零的整数窄化警告，改为显式uint8_t保持原语义。
- 新增渲染目标关闭C++异常，实际includes、链接response、对象/静态库、符号与DLL依赖留证。动态依赖为Windows系统D3D12/DXGI/USER32/KERNEL32。

### 后续范围

当前UI与GPU提交共享拥有线程。多线程录制、通用材质/资产、采样器、GPU流送、GI、阴影/后处理仍按M4后续阶段实现。Compute与Graphics已实际交接，GPU并行重叠收益尚未测得。DRED故障注入和最终4K/UE对照均未验收。

### 本机重现

```powershell
python engine_next/Tools/BuildVisualRuntime.py --build-dir build/engine_next/m4-1 --run-tests
build/engine_next/m4-1/next_visual_client.exe --validation --frames 240 --hidden --exercise-resize --deterministic --report build/engine_next/m4-1/Validation.json --capture build/engine_next/m4-1/Validation.ppm
```

Python使用tools/run_issue_gate.ps1 -ProbeOnly发现的实际3.11+解释器。独立窗口可直接从Release运行next_visual_client.exe，WASD移动视图，Esc请求退出。--deterministic用于固定时间的重现采集。

证据为data-collection/engine-next-visual-runtime-m4-1-verification-20261115.json、build-impact.json、capture-final2-20261115.json及video-final2-20261115.json。正式CI、PR与main回读待本候选发布后追加远端回执。
