# 谛听数据采集目录

本目录用于保存已授权采集材料的来源索引和交接结果，供谛听读取。目录和配置不是谛听服务上线或读取成功的证据。

- `sources.json`：真实数据源及读取接口。
- `requests/<request-id>/<unique-id>.json`：经校验的需求事件索引，含源相对路径、SHA256、租户、原事件 ID 和原始身份来源；只追加，不覆盖。
- 后续原始附件按需求隔离，在获得该材料留存授权后添加，不能自动复制凭据、私有聊天或机器路径。

唯一事件事实仍在 `olympus-hermes-data/`。Hermes 与谛听使用同一读取入口；索引不是新事件、不会重复计数。索引覆盖所注明的需求和采集时刻；不得据此宣称历史或远程 Issue 全量覆盖。源文件摘要发生变化时停止使用旧索引并重新核对，不改写历史索引。

采集命令：`python customizations/components/issue-workorders/work_items.py collect --request-id REQUEST_ID`。只有存在真实事件且全库校验通过才生成索引。
