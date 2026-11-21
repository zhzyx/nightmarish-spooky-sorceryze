# U07　从 2D 和 3D 选区引用场景节点

在 2D 或 3D 编辑页选中场景节点，通过命令面板打开 AI 工作台。输入区按编辑器的选择顺序显示本轮引用数量和节点路径，悬停可查看各节点的完整定位和场景文件 SHA-256。同名叶节点通过各自的父路径区分。每项沿用 C05 的 `kind`、`object_id`、`revision` 格式，定位为 `res://场景#相对节点路径`。每条消息至多引用 16 项，超过时提示缩小选区。[原工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1828) · [消息契约](gonggong-ai-workbench-c05.md)

打开侧栏时捕获一次选区。继续编辑、移动选区或切换侧栏布局时，当前草稿保留已捕获的引用。发送前核对原场景实例、各节点实例、相对路径与场景文件字节，任一成员失效时保留整组引用及用户正文。用户可点击引用移除整组，重新选择后再次调用工作台命令。发送按钮受理草稿时冻结整组，在会话历史按消息回读。需要精确修订的节点应来自已保存场景。[失效语义](gonggong-ai-workbench-c08.md)

## 定向验证

从仓库根目录使用当前候选的编辑器运行。夹具启动隔离的 headless 编辑器，通过命令面板、草稿控件和原生发送按钮访问本机回环模型。分别核对 2D 和 3D 的单选与同名节点多选、历史、实际请求，以及多选中非首节点改名后的拒绝和移除。重启进程后还会回读含三个节点的原草稿。测试进程需要清空继承的 GONGGONG_WORKSPACE。

```sh
python -X utf8 tests/editor/run_tianshu_spatial.py --godot "$EDITOR_BINARY" --scene-selection --report "$OUT/scene-selection.json"
python -X utf8 tests/editor/run_tianshu_spatial.py --godot "$EDITOR_BINARY" --references --report "$OUT/spatial-reference.json"
```

[候选与实测回执](../data-collection/gonggong-ai-workbench-plan1-u07.json)
