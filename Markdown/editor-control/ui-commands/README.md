# 通用 UI 输入命令化

完整协议见 [AI 编辑器操作接入](../../../tools/EDITOR_CONTROL.md)。本页保留常用执行顺序和关键约束。

## 执行顺序

1. 用 `find_targets` 发现当前目标。
2. 用 `describe_target` 读取目标当前支持的 `actions`。
3. 构造 `engine_operation`，通过 `route_engine_message` 或本机客户端提交。
4. 按响应等待确认、查询状态并回读实际结果。

声明式消息示例：

```json
{
  "intent": "engine_operation",
  "request_id": "open-project-settings-001",
  "source": "my-agent",
  "operation": {"action": "open_target", "target": "project_settings"}
}
```

不同操作使用新请求 ID；同一来源和 ID 不得用于不同内容。自然语言规划结果不代表操作已执行。

## 常用动作

| 动作 | 用途 |
| --- | --- |
| `open_target` / `reveal_target` | 打开并显示页面或目标 |
| `focus` / `highlight` | 聚焦或高亮目标 |
| `set_text` | 写入受控文本 |
| `set_value` | 设置合法范围内的有限数值 |
| `select_option` | 按索引选择可选项 |
| `press` | 调用按钮原生激活逻辑 |

## 本机 CLI

在包含客户端的实际仓库根目录运行：

```powershell
python tools/editor_control_client.py --project D:/MyProject capabilities --query "Project Settings"
python tools/editor_control_client.py --project D:/MyProject route --message operation.json --wait 60
python tools/editor_control_client.py --project D:/MyProject status open-project-settings-001 --source my-agent
```

多编辑器打开同一项目时用 `--instance PID` 明确实例。`--wait` 到期不等于取消，不能因此重复执行。

## 权限与隐私

- 写入和按钮操作必须取得宿主确认，或由用户事先启用自动执行。
- 确认绑定目标实例和旧值；目标、值、可见性或可用状态变化后不得沿用旧确认。
- 密码输入、授权控件、确认弹窗及被排除子树不进入普通 UI 目录。
- 发现文件含私有随机会话令牌，不得交给模型、上传或提交 Git。
- 桥接仅使用当前项目的回环地址；以结构化响应中的实际状态判断结果。

工作台在模块对话中发送原生脚本选区、场景节点或资源后，按账号、工程、模块、事项及会话保留目标。后续回合以磁盘内容判断修订，并把原生保存回执中的操作者绑定到同一摘要。工程内的依赖独立计算版本；外部写入只登记可核实的内容。[脚本选区](../../../design-docs/gonggong-ai-workbench-e03.md) · [场景和资源](../../../design-docs/gonggong-ai-workbench-e04.md)

选择「继续当前工作」时，模块草稿保留本次会话已发送的目标和人工保留意见。接续输入从这些目标的起始内容比较到当前可读修订。动画按片段、轨道类型、节点属性路径和同名序号区分，键按实际时间定位；超过观察上限时回报明细不可用。[时间线修订](../../../design-docs/gonggong-ai-workbench-e05.md) · [接续输入](../../../design-docs/gonggong-ai-workbench-e06.md)

脚本接续候选从原生编辑器审阅并保存。动画候选支持固定落地关键帧、压缩前段、回放两个修订并恢复时间线位置。[操作与验收](../../../design-docs/gonggong-ai-workbench-edit-candidates.md)


## 天璇原生工作区

需求：Godot 内完整使用天璇，同时保留独立 Web 端、现有账号权限与数据。主工作区和可停靠侧栏共享编辑器持有的会话及控制器；视图只采集操作和呈现状态，关闭视图不结束任务或删除草稿。原生主题、局部语言域与窄栏布局不修改 Godot 的全局语言；作者输入保持原文。

做法：内嵌 GDScript 属于原生构建输入，变更后重建并验证编译产物。草稿按服务、租户、账号和记录隔离，保留提交编号与基线；断线或未知回执先核对服务记录。文档合并必须使用同一远端版本的标题和正文，并同步聚焦编辑框；异步成功仅清理对应提交的草稿。PR 审查与合入绑定提交 SHA 和目标分支，发布草稿保留内容基线；上游未提供原子条件写时明确其检查后竞态边界。项目绑定、选区上下文、定位及资源导入由编辑器控制器执行，导入不得覆盖用户现存资源。

源码与验收映射见[天璇原生 UI 设计](../../../design-docs/tianxuan-native-ui-20261123.md)。真实服务、编译后 headless 控件、Web 浏览器、Windows/macOS 构建和显示/IME 各自留证，不能互相替代。
