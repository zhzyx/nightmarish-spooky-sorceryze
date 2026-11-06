# 03-editor 引擎内工作流编辑与发布

稳定需求 ID：ainative-art-03-editor-20261106

父设计：[AINative 美术与人物工作流](../ainative-art-pipeline-20261106.md)。父工单见总设计回执；本页仅用于本子项身份。

范围：节点编辑、上下文补充、任务进度、预览、人工确认、Godot Resource/Scene 发布。

验收：在引擎内保存重开图；图片与 Mesh 可预览；失败保留源资产；发布文件可重导入；编辑器不阻塞。

前置：01-contracts, 02-executor。

非目标：其他子项的完整实现；任务登记不表示功能通过。

主责：Codex / kaiyunxue（当前操作者）；目标 main；先 intake-only，交付通过正式门禁和精确候选 CI。必要检查：契约单使用单元测试，其余使用该范围内真实资产、编辑器回放或目标工具回读；保留失败证据。

## #144 实现与实际验证（2026-11-06）

交付位置：`samples/ainative-workbench/addons/ainative` 可安装 EditorPlugin；示例工程可直接由 Godot 打开或运行主场景。安装与操作见示例 README。`tools/ainative/editor_host.py` 以 spec/result 文件桥接已合入的 Executor；所有 Python 命令使用 OS.create_process，进度、取消、重试读取真实持久状态。`editor_demo.py` 是明确标注的本地导入/复制 Provider，不生成 AI 资产，不替代 #145。

GraphEdit 支持节点增加/删除/移动、连接/断开、JSON 参数、文字与图片上下文、JSON 保存重开。机器级 Python/script/trusted factory 位于 Godot user:// 本机设置，图不携带执行配置；无凭据输入且拒绝常见凭据键。不要把秘密粘贴到自由文本上下文。运行前从本地源文件快照字节，GLB/glTF 必须自包含，所有外部 URI 拒绝。

图片由 ImageTexture 实际预览；GLB/glTF 由 GLTFDocument 解析至独立 3D SubViewport，按 Mesh AABB 构图。人工确认绑定 run、artifact revision token、编码字节 SHA256 和目标路径。后台回验后复用 publish_new 原子 no-clobber 发布新 .tres/.tscn，现有文件或链接不覆盖；失败不修改来源。reconcile 暂停并显式 Resume 单次查询，不无限自动提交；create 期间取消也绑定新创建运行。退出回收自有子进程，持久状态保留。

实际使用现有 `godot.windows.editor.x86_64.console.exe`（4.8.beta.custom_build.ced0368bb）运行插件启动、headless 行为回放以及 NVIDIA OpenGL 实际渲染回放。`acceptance.gd` 报告 `AINATIVE_ACCEPTANCE failures=0`：保存重开语义保持、畸形边不替换当前图、保存拒绝源 PNG、真实 PNG/glTF/GLB 读取、后台心跳持续、失败/取消/重试真实状态、立即取消 create、人工确认前不生成目标、重复发布不覆盖、发布图像 .tres 与 Mesh .tscn 再加载包含真实资源、源摘要不变。Python host 测试通过：绑定确认、防 staged 篡改、旧确认拒绝、no-clobber、外链 glTF/GLB 拒绝、factory 不从图读取。回放中最初字符串比较因 JSON 数字 int/float 表示差异失败，已改成 JSON 语义比较；不是放宽节点/连线/参数/上下文内容验收。

限制：首版单 source/result 端口与 JSON 参数编辑，不包含通用节点发现/调色板；trusted factory 可接兼容定义。大型模型 Godot 解码/序列化仍在主线程，耗时 Provider/后台状态操作不占主线程。只支持内嵌依赖的 GLB/glTF；未宣称动画、骨架或材质生产质量验证。现有本地 demo 的 fail=true 重试会再次失败，实际 attempt 递增可观察。原子发布要求目标文件系统支持 hardlink。行为回放的程序确认是测试，不代替业务人工验收。
