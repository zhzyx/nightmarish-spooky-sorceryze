# 并发候选交接与基线复核

父单 [#246](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/246)，子单 [#249](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/249)。本次用户要求执行 #227 的全部优化。本单写入已有的协作者签发入口及回归；司南派发、夸父事件和框架准入由各自责任者处理。

从仓库根运行原 `customizations/components/issue-workorders/writer_submit.py` 提交命令。新 PR 展开签发人、基线、源候选、签发 head、树与相对基线的写入路径（含删除）；路径清单较大时显示完整比较链接。精确路径和归属也随命令结果返回。重试复用同一已签发 PR；已合入的同一提交回读 main 接收情况。

合入前或恢复时运行 `python customizations/components/issue-workorders/writer_submit.py --repo . --inspect-pr PR编号`。入口从 GitHub 签名消息与 Git 对象重建交接，兼容旧版 PR 正文。读出签发基线、实际回读的 main、上游变化数、同路径或目录/文件冲突范围及下一动作；区分路径交集与实质返工（未知）。即使路径不交叠也需检查接口依赖，使用原门禁和 CI。这个只读快照可用于合入前后复核，调用者仍须匹配 head 与分支保护。

已合入时先验证接收提交在远端 main 上；标准双父合并按合入第一父计算当时的并发范围，单父等无法还原该时点的接收方式保留未知。交付差异按本单写入路径对比签发树与实际接收树，不用之后的主线编辑倒推原交付。

验收覆盖正常签发、同一候选重试、权限、签名和旧 PR、主线前移、文件与目录冲突、合入后又有新写入的回读。回归使用真实临时 Git 历史并隔离 GitHub 写操作。实际签发和主线接收由父单绑定真实回执。
