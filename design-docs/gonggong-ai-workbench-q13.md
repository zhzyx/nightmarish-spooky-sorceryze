# Q13 工单和设计组合验收

[原卡 #1723](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1723) · [方案一 Q13](gonggong-ai-workbench-plan1.md#q13) · [逐项回执](../data-collection/gonggong-ai-workbench-plan1-q13.json)

## 从模块路线图读回来源设计

本次沿用 D10 的开桥设计和两个拆单验收条件。在独立的天璇项目 `studio/bridge` 中，设计师签认文档 v1，以第 1 段创建「操作拉杆」，以第 2 段创建「桥面展开」。两单挂在「桥梁交付」下。「桥面展开」依赖「操作拉杆」。随后将文档改为 v2，把桥面的动作由打开改成关闭。两个版本的差异能检出工单误读最新设计的问题。

| 在 Windows 原生工作台操作 | 预期与实测 |
| --- | --- |
| 从命令面板打开工作台，在模块路线图展开「桥梁 → 未设置里程碑 → #1 桥梁交付」 | 原单列出 #2 操作拉杆和 #3 桥面展开，与天璇重新打开数据库后的父子关系一致。 |
| 在同一路线图打开 #3 | 详情的负责人、状态、内容修订、验收条件与独立查询一致。详情显示父单 #1。上游行指向 #2 的唯一 ID，显示尚未验收，当前受阻。 |
| 在 #3 的评论区选中审阅记录 | 评论 ID、作者、时间、所属工单及显示正文与持久记录一致。 |
| 使用「阅读来源设计 · v1 · 第 2 段」再打开「版本历史」 | 打开已签认文档的 v1 第 2 段。历史差异指向同一文档的 v1 和 v2，显示 opening 改为 closing；v2 没有继承 v1 签认。 |

## 复验与接收依据

运行环境需要天璇服务的 Python 依赖、仓库代码以及带工作台的已编译编辑器。在仓库根目录运行，命令末尾是本机接收 JSON 的输出路径。

```powershell
python -X utf8 tests/editor/run_workbench_issue_design_trace.py --godot <编辑器路径> --report q13-trace.json
python -X utf8 tests/editor/run_workbench_issue_chat_comment.py --godot <编辑器路径> --report i16-recheck.json
```

第一项启动隔离的真实编辑器、天璇 HTTP 服务和 SQLite 数据库，核对原生控件、详情接口与重开的数据库。第二项使用 I16 自身的两张同名工单，咨询产生零条评论，授权后仅选中单收到一次发表请求，三个读取入口返回同一评论。两项均使用 [PR #2021 已接收的 Windows 编辑器](https://github.com/zhzyx/nightmarish-spooky-sorceryze/pull/2021)，SHA-256 为 `959b9558c58ae549a72516832ac350d6539bcea31445b8a3004b982665364d78`。

I19 的 Mac 原盘点列出 18 项，其中 15 项在当时已关闭。Q13 保留每一行的原状态和证据，并回读 GitHub 的 completed、主线修订及每项验收文件的 Git blob。余下三项由后续合入接收。[I08 路线图](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1751#issuecomment-7071715018)、[I18 附件上传](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1759#issuecomment-7071728041)、[I16 授权评论](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1757#issuecomment-7074402569)。

回执中的 `native_sample` 和 `i16_recheck` 记录本机操作。`issue_capabilities` 记录 I01–I18 的历史接收，`other_prerequisites` 记录 D08、D11、D12、D13 和 I19 的接收来源。K02 可用设计 ID、固定版本、段落、工单编号和内容修订回读同一条关联。[完整验收回执](../data-collection/gonggong-ai-workbench-plan1-q13.json)
