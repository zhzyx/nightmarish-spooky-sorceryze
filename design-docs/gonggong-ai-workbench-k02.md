# K02 从设计修订抵达天璇工单

Windows 工作台的里程碑样例沿用 Q13 的开桥设计。设计正文第二段引用已验收的 GitHub 旧单 #1723。验收工具在隔离项目中通过历史归档入口读回该单的标题、状态和正文，再从编辑器打开设计、签认 v1、将两条验收条件映射到桥梁模块。签认与拆单各确认一次。天璇给「操作拉杆」和「桥面展开」各分配独立编号。具体编号、业务 ID、签认人、段落及接收时间见[本次回执](../data-collection/gonggong-ai-workbench-plan1-k02.json)。

编辑器把正文改到 v2，分别从两个工单详情打开来源。两单仍显示签认 v1 的第 1、2 段，v2 保留自己的签认状态。随后从这两个编号的原生详情发起咨询，切单后重开第一单，核对原会话、原消息与当时的工单内容修订。回执记录咨询使用的隔离模型传输、实际天璇应答以及执行数。历史归档与 GitHub 原单在验收后再次读取，逐项核对原件，天璇业务库中只保留两张新单。[Q13 桥梁样例](gonggong-ai-workbench-q13.md)

I19 的 Mac 盘点在当时接收了 15 项，余下 I08、I18 和 I16 由后续主线修订接收。本次按 Q13 保存的 18 个原始完成评论逐项回读 GitHub 的 completed 状态、接收修订对主线的祖先关系、验收文件的 Git blob。每行保留历史状态和当次接收链接。原单的四张直接前置也单独回读。[I19 原盘点](../data-collection/gonggong-ai-workbench-plan1-i19-mac-round9.json) · [逐项接收依据](../data-collection/gonggong-ai-workbench-plan1-k02.json)

## 复验

从有天璇服务依赖、已登录 gh 且拥有主线历史的仓库检出运行。将编辑器路径替换为带工作台的签发包。工具复制到临时目录，使用 headless 编辑器、本地 HTTP 天璇服务、隔离业务数据库和只读 GitHub 查询。每次运行都会产生独立的文档、工单和会话标识。

```powershell
python -X utf8 tests/editor/run_workbench_design_milestone.py --godot <编辑器路径> --report k02-recheck.json
```
