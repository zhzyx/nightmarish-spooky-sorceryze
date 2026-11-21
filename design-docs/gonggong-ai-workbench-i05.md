# I05 工单评论与引用

工单 [#1788](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1788) 对应[方案一 I05](gonggong-ai-workbench-plan1.md#i05)。用户在已经读取的工单详情中发表评论，选中一行可以查看完整正文、回复该评论，或跳到它引用的原评论。[前置 I02 验收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1854#issuecomment-7066884069)

## 显示和恢复

原生控件 `editor/docks/workbench/issue_actions/issue_comments.gd` 监听 `WorkbenchIssueDetail.detail_changed`。详情清空时清除旧行、正文和草稿并隐藏控件。每次加载绑定当前详情代次，迟到的读写回执不能覆盖另一个工单。列表按服务返回顺序显示作者姓名和正文首行，悬停可见作者 ID 与写入时间。选中项可在限高的滚动区域中阅读完整正文，并支持逐级返回原评论。

编辑器用项目元数据记录选中的评论 ID，键由登录用户、业务项目和工单 ID 生成。重开工单时按服务实际返回的评论 ID 选中并滚动到原行。元数据仅保存位置，线程内容每次从经认证的服务读取。

## 天璇接口

沿用 `GET/POST /api/v1/issues/{issue_id}/comments`。普通评论只需要 `body`。回复携带 `parent_id`，服务核对父评论属于同一租户、同一工单。作者取自已认证会话，现有读写权限与祖先工单访问规则继续生效。`issue_comments` 保留原有写入记录和排序，新增的 `issue_comment_replies` 表只记录实际回复的引用关系。历史评论可直接作为回复目标。

传入可选的 `call_id` 时，天璇使用同一事务记录评论、父引用、事件和请求回执。相同账号重试同一份草稿会获得原评论 ID。已成功写入的相同正文仍可由新操作作为独立评论发表。

## 构建和核验

总单已在服务基线 3034a7ef9 验证两位作者依次留言，重启后评论 ID、顺序和作者一致。本次在原生详情中验证选中、回复与返回原评论。[总单服务回读](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1709#issuecomment-7066453423)

SCons 将动作目录内 GDScript 生成 `IssueActions.gen.h`，由 `AIWorkbenchSidebar.cpp` 嵌入编辑器。宿主注册来自 I03。回退时恢复上一组已验证的编辑器与服务，旧服务仍能读取原有评论表。历史服务界面不显示新回复关系。

静默验收使用 `tests/editor/run_workbench_issue_comments.py --godot <候选编辑器> --report <输出路径>`。它在临时目录启动真实天璇账号服务，用两个账号四次启动隔离的原生编辑器，逐行核对显示内容和独立重开的数据库，验证引用跳转与账号的位置恢复。[定向验证回执](../data-collection/gonggong-ai-workbench-plan1-i05.json)

I16 [#1757](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1757) 可沿用同一服务接口和稳定评论 ID。交付由父会话核对精确候选、目标接收与 GitHub 关闭回执。
