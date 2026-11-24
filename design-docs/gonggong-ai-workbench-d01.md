# D01　从编辑现场发起咨询

编辑者从命令面板选择「Open AI Workbench」时，若当前会话没有与项目、原单、会话及代次匹配的原生任务授权，侧栏会勾选「仅咨询」。可以直接问「请改代码」，再在当前输入框追问。咨询的每条消息固定自身模式，沿已有会话发送；允许读取时，模型只能使用已有的只读工具。未授权的操作仍经原有执行门禁。[工单 #1862](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1862) · [设计条款](gonggong-ai-workbench-plan1.md#d01)

展开到完整工作台并返回侧栏时保留本会话刚选的模式。切换或新建会话时重新进入咨询模式，避免沿用另一会话的选择。侧栏再次从编辑现场打开时重新核对任务授权。原生聊天的独立开发入口及逐条授权规则见[咨询输入约定](../Markdown/editor-control/consultation-input/README.md)。

在仓库根使用当前候选的裸编辑器运行以下回归。第一个用例在六次独立进程中验证侧栏状态、快捷入口和往返，第二个用例使用本机回环模型验证咨询的读写边界与显式恢复队列。

```sh
python3 tests/editor/run_ai_chat_tab_order.py --godot "$EDITOR_BINARY" --workbench-command --report "$OUT/layout.json"
python3 tests/editor/run_consultation_only.py --godot "$EDITOR_BINARY" --out "$OUT/consultation.json"
```

Mac 端另在签名应用内通过原生侧栏连续发送两轮，检查两轮各自的实际模型消息、可用工具、回复及临时项目文件的摘要。[本次定向验收数据](../data-collection/gonggong-ai-workbench-plan1-d01.json)
