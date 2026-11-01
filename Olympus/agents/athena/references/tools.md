# 雅典娜兼容工具

代码位于 integrations/athena-legacy，按框架根路径解析。仅保留五个运行代码文件；旧 Agent、skill、模板和私有宙斯副本不进入活动目录。runtime/src/production.mjs 的恢复读取统一指向共享 upstream/zeus。

命令：node integrations/athena-legacy/athena.mjs 目标仓库 init、new、team、approve、tickets、refresh、work。Node 与 Git 为依赖；会写目标仓库文件与本地 Git，必须有真实授权。feature-memory.mjs 为可选索引，已有项目索引优先。

确认按 direction、planning、design 顺序，收据包含 actor、quote、source、time 并绑定文件哈希；真实身份由宿主核验。建单前 team 指定唯一主要负责人和职责明确的协作方；定版 production.json 的显式 tasks 使用 key 和 dependsOn。

工单和文档从同一账本刷新；watch 为前台进程，不是后台同步。批准文件变更须保留旧基线、建立修订并重验；派发、ack 和独立验收都需真实证据。状态仍待宿主执行时不得宣称已制作完成。

CLI 本身不验证奥林匹斯准入凭据或宿主身份，文件可被直接修改；调用者和宿主必须核验通行证、权限、锁及质量规则。旧包保存在历史归档，完整参数见兼容 CLI 源码或 help；不自动导入旧提示词。
