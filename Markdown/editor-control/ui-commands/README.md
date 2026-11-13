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
