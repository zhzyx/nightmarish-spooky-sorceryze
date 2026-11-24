# C08　3D 工单聊天中的引用失效

在 3D 视图选中已保存场景中的模型，并从天枢空间面板打开关联的「工单聊天」。原有会话的输入框显示本轮编辑器引用。场景中的节点由场景文件、相对节点路径和修订摘要标识；具有独立源文件的模型另记资源路径及摘要。[工单 #1839](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1839) · [设计条款](gonggong-ai-workbench-plan1.md#c08) · [单条消息引用契约](gonggong-ai-workbench-c05.md)

发送前编辑器核对当前场景、节点实例、路径与源文件。若换了场景、原路径已经失效、同名节点替换了原实例或资源已删除，输入框显示失效并保留草稿。发送时还会回读源文件的字节摘要。点击失效引用可以移除，再从原生入口重新选择。已发送消息保存当时的引用和修订。重开编辑器时，原进程的节点实例无法再核实，恢复的草稿要求重新选择，旧版模型草稿中的用户正文保留。

## 定向验证

在当前工作树根目录用候选的裸编辑器运行以下命令。空间工单用例覆盖原入口与重启；引用用例实际发送一次有效消息，在隔离回环模型处核对原工单、节点与资源摘要，并回读历史。

```sh
python3 tests/editor/run_tianshu_spatial.py --godot "$EDITOR_BINARY" --report "$OUT/spatial.json"
python3 tests/editor/run_tianshu_spatial.py --godot "$EDITOR_BINARY" --references --report "$OUT/references.json"
```

通用 2D/3D 选区进入统一侧栏及文件系统、检查器的引用适配分别由 U07、U09 验收。[候选与实测数据](../data-collection/gonggong-ai-workbench-plan1-c08.json) · [U07 #1828](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1828) · [U09 #1830](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1830)
