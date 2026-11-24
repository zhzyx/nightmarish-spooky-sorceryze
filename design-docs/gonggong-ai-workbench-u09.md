# U09　把检查器与文件系统选择加入 AI 草稿

打开命令面板中的 **Open AI Workbench**。侧栏的 **Attach Resource** 菜单提供两个入口。**From FileSystem** 添加文件列表选中的项目文件，**From Inspector** 添加检查器当前打开的资源。可先在文件系统选中 `res://north/SameGradient.tres`，再在检查器打开 `res://south/SameGradient.tres`，分别使用两个入口将它们加入同一条草稿。草稿列出完整路径，悬停可查看所有引用。重复选择同一资源只保留一条引用。[工单 #1830](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1830) · [方案一 U09](gonggong-ai-workbench-plan1.md#u09)

已保存资源使用项目路径与文件 SHA-256。内嵌资源保留含子资源标识的路径，并取宿主文件的摘要。没有文件路径的资源显示「临时资源」，定位串包括本次编辑器运行标识、类型和实例 ID。它的修订基于运行期身份及检查器编辑版本。关闭编辑器后，临时定位串只供回看当时的消息。

切换选区时，草稿保留已添加的对象。发送沿用 [C05 消息快照](gonggong-ai-workbench-c05.md) 与 [C08 失效处理](gonggong-ai-workbench-c08.md)。文件删除或内容改变、临时对象释放或另存，以及重启后恢复的原选区要求重新选择。失效时发送保留正文，点击引用可移除整组，再添加新选择。每条消息可携带最多 16 个对象。

在工作树根目录运行 `python -X utf8 tests/editor/run_workbench_resource_selection.py --godot <候选编辑器> --report <报告.json>`。探针在独立项目通过普通侧栏实际发送，并比较模型收到的引用与聊天历史。[候选与定向验证](../data-collection/gonggong-ai-workbench-plan1-u09.json)
