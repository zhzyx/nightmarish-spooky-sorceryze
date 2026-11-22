# E08 在原生段落建议窗口核对并解决重叠修改

已生成的 AI 段落与协作者保存的正文重叠时，原生建议窗显示基线、人的当前版和 AI 片段。选择保留人的版本、使用 AI 片段或编辑第三版后，按所见的当前修订确认保存。服务保留未冲突区域和原 Markdown 分隔符。Mac 窗口分别演练三种决定，并为每种情况丢弃首次写入响应，用原调用标识核对同一已保存修订。运行 tests/editor/run_workbench_paragraph_suggestion.py，分别传入 --resolution 0、1、2，再运行原有无参数冲突回归。

[设计条款](gonggong-ai-workbench-plan1.md#e08) · [实机验收回执](../data-collection/gonggong-ai-workbench-plan1-e08.json)
