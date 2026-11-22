# G18 多宝写入入口回退演练

在仓库根目录运行以下命令。脚本在新建的临时目录中建立原 Git 仓的副本、多宝写入副本和租户路由数据库，输出可归档的 JSON 回执。

```sh
python3 customizations/components/tianxuan/migration/rehearse_write_rollback.py
```

演练先保存原入口、两端所有分支与标签的提交编号。切换路由后，多宝通过 GitService 分别向 main 和 topic 写入。恢复时从磁盘重读原路由与两端水位，验证每条分支可快进，将两条分支原子推回原端，核对全部引用后恢复原路由。最后从原入口克隆并追加一次提交，验证其直接父提交是切换期间产生的 main 提交，并回读 topic 的内容、原标签和 Git 对象完整性。

[设计条款](gonggong-ai-workbench-plan1.md#g18) · [Mac 实机回执](../data-collection/gonggong-ai-workbench-plan1-g18.json)
