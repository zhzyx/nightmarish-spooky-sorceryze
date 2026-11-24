# I16 将工单咨询回复发表为评论

用户从工单详情打开咨询，取得一条回复后，可以选择“将本轮回复拟为工单评论”。对话框显示原单编号、标题和待发表的完整正文。点击“授权发表”后，天璇使用当前登录身份调用 I05 评论工具。发表成功时，原生详情从评论列表读回并选中新评论。手写的未发表草稿继续保留。切换工单、退出账号或取消预览后，原来的确认失效。[I16 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1757) · [I05 评论与引用](gonggong-ai-workbench-i05.md)

## 执行条件

服务的 `POST /api/v1/workspace/conversations/{key}/issue-comment` 接收会话版本、回复 ID、原单 ID 与修订、预览正文和适用的阶段签认修订。它从认证会话取得租户与用户，重算工单咨询的私有会话 ID，检查最后一条回复、原始引用、项目和模块，再按最新工单权限写入评论。普通工单沿用 I05 编辑者权限。

设计拆单复用 A03 的 `task_stage_authority`。这项适配器在产品代码中只绑定“工单评论”阶段与评论写入。服务检查来源设计版本、工单定义、负责人、签认人、阶段、到达条件、目标与签认修订。当前签认人须与授权发表的登录人一致。负责人要为其他阶段做咨询时仍可得到草稿。来源设计不可读、目标未定义、阶段未确认、已撤销或预览取得后重新签认时，服务拒绝写入。[A03 阶段授权](gonggong-ai-workbench-a03.md)

服务在同一次 SQLite 写事务内完成检查、调用 `add_issue_comment` 和保存该轮操作回执。I05 的调用标识由会话和回复 ID 派生。回复记录保存评论 ID、授权人及确认时使用的修订。连接中断后，相同确认可取回同一条评论。原生详情按服务返回的评论 ID 回读，按完整记录核对结果。编辑器内嵌脚本通过 `module_selector.gen.h` 和 `IssueActions.gen.h` 构建，回退时还原对应编辑器与服务。既有 I05 评论保留在原表。

## 验证与来源

在天璇 Python 环境运行 `python tests/editor/run_workbench_issue_chat_comment.py --godot <候选编辑器> --report <报告路径>`。该用例启动带真实账号和 SQLite 的隔离服务，使用受控模型回复、两个独立启动的静默编辑器及两张同名设计工单。它先检查两份咨询草稿以及空评论表，再经确认对话框发表一份，从原生评论控件、HTTP 和独立 SQLite 连接比对评论 ID、作者、正文与所属工单。它也测试切换同名工单、修订失效、撤销签认、阶段不匹配、其他账号以及相同请求重试。[定向用例](../tests/editor/run_workbench_issue_chat_comment.py) · [本次实测回执](../data-collection/gonggong-ai-workbench-plan1-i16.json)

I05 的 Mac 观察记录了两位作者的评论顺序和稳定 ID，以及当时编辑器的回复定位缺口。后续 I05 已由原生详情验收。本次定向验证使用 Windows 工作树。[Mac 上游观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1788#issuecomment-7067782982) · [I05 主线接收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1788#issuecomment-7068756315)
