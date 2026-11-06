# 04-generators 图像与 Mesh 生成节点

稳定需求 ID：ainative-art-04-generators-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：文生图、图生图、图生 Mesh、文生 Mesh；文字与图片可追加到各阶段。

验收：至少一个实际 Provider 完成四种流程并留版本/参数/来源；mock 不能替代真实生成验收；缺能力显式返回不支持。

前置：02-executor, 03-editor。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。

实现（#145）：`tools/ainative/comfy_provider.py` 以本机可信配置连接 ComfyUI HTTP；
四种节点已进入工作台选择器，保留 local-copy 演示。配置示例与真实运行命令见
`tools/ainative/README.md` 的 Real ComfyUI provider 节。部署顺序为先本机
4070 Ti 12GB，之后可在同一 HTTP 后端协议下迁移服务器；迁移必须更新模型、
后端版本与配置身份，不能把旧缓存当成新服务结果。

图像使用 SD-Turbo；Mesh 使用 Hunyuan3D-2mini 图像条件。文生 Mesh 在同一
Comfy prompt 中组合图像生成与 Mesh 生成；图生 Mesh 追加文字先经 SD-Turbo
图像编辑。单图上下文作为 img2img 初始图像或 Hunyuan vision 输入；多图（包括
source 加另一个图片上下文）明确返回不支持。Mesh 产物目前为无纹理几何；
不声称已有纹理、骨骼或人物绑定。请求、实际参数、输入摘要、模型 SHA256、
Comfy commit、配置/Provider/工作流指纹与 PNG/GLB 字节和摘要一起持久化。

持久化提交意图、未知回执只查询 queue/history、不盲目重投；本地共享存储提供
幂等协调，ComfyUI 本身不保证全局幂等。取消仅删除本任务排队项；运行中采用
本地隔离，不调用可能中断其他用户任务的 `/interrupt`。所有结果限定到已确认
所属的 prompt 和 output 节点，同源下载且拒绝路径穿越、任意 URL 和重定向。

验证分层：原 39 项测试保留；增加真实 localhost HTTP 故障测试（不运行模型），
覆盖断连回执、恢复、缓存身份、取消、恶意输出与终态竞态。Godot headless
acceptance 已验证图快照保存/重开、后台心跳、PNG/GLB 预览、发布不覆盖及
失败/重试/取消恢复。真实模型四流程验收由本机运行回执另行记录，协议测试
不替代此验收。

本机实际验收（2026-11-06）：53 项 Python 测试通过，独立审查及受影响修复
复核通过。RTX 4070 Ti 实际运行 SD-Turbo 和 Hunyuan3D-2mini，四种流程均
产生持久 PNG/GLB；真实 Godot OpenGL 回放完成预览、确认发布及资源重载，
`AINATIVE_LIVE_ACCEPTANCE failures=0`。工作台保存并重开包含文字和图片
上下文的流程后，实际 Run 再次生成并预览，`AINATIVE_LIVE_GENERATE failures=0`。
Godot JSON 的整数浮点传输只在编辑器边界按整数 schema 规范化，不放宽核心
契约。证据、各次模型/参数/来源及产物摘要见
[验收记录](../../data-collection/ainative-generators-validation.json)。

mini 模型使用 latent resolution 512、20 steps、octree 128；surface net
提取后平滑法线。实际机器人 Mesh 为 33,635 顶点，头盔为 59,628 顶点。
这些是原始生成几何：机器人仍有地面/阴影底座残留，薄壳头盔存在孔洞与粗糙
表面，未通过生产拓扑、绑定或动作验收。#146 承接标准化和拓扑诊断；本项
不将 GLB 可加载等同于可直接用于角色动画。图像参考也不保证身份或姿态保持。

API依据：ComfyUI 官方源码 `comfy_extras/nodes_hunyuan3d.py`、
`nodes_video_model.py`、`nodes_save_3d.py` 与 `comfy_api/latest/_ui.py`；本机
安装版本以配置 `backend_revision` 为准，运行前按实际 `/object_info` 校准。
