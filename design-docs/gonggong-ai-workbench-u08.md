# U08　从脚本选段打开工作台

在脚本编辑器中选择文本并打开 AI 工作台。引用记录脚本的项目相对路径、从 1 开始的行列范围、当时编辑缓冲区的 SHA-256 和所选文字。组合工作台保留原有脚本引用，可继续添加不同定位的选段，发送时将所选内容和修订一并冻结。点击输入框上方的引用可在发送前移除。[工单 #1829](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1829)

Windows headless 编辑器通过命令面板从两份同名脚本打开同一侧栏，切换脚本后分别发送。测试逐条核对实际回环模型收到的用户消息，第三次先移除引用并确认消息只含正文。[原生探针](../tests/editor/workbench_script_selection.gd) · [验收回执](../data-collection/gonggong-ai-workbench-plan1-u08.json)
