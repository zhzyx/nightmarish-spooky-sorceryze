# 修复聊天工具的大文件分段读取

<!-- gonggong-request:large-file-read-20261107 -->

来源：原需求 Issue #387 的引擎内工作流实测。用户授权发现流程问题后停止并修复；本单只修复读取缺陷。

## 已复现

read_file 对 ai_chat_dock.cpp 传入 offset/limit，仍在切行之前读取完整文件，超过 256 KiB 后拒绝，阻止 Agent 查阅引擎自身源码。全文件写入及快照上限继续保持。

## 范围与验收

- 在有明确 offset/limit 时允许从有总扫描上限的大 UTF-8 文件读取有限行数，内存及返回内容均有界。
- 严格校验 UTF-8、NUL、offset/limit、超长行、扫描和输出预算；保留一致的行号/截断元数据，不返回被截断的码点。
- 默认整文件读取、写入及快照仍受 256 KiB 限制；只读查询不创建快照。
- 针对大于 256 KiB 的真实源码、UTF-8 边界、非法编码及容量边界运行测试；独立审查后提交并通过 PR 推进 main。

## 验证

Issue：[#392](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/392)。

macOS arm64 候选编译通过；真实编辑器离线 HTTP 工具循环 21 项通过，见 `data-collection/large-file-read-20261107.json`。测试使用候选副本及 `_sc_` 自包含设置，不修改真实全局设置。读取不承诺并发同长度改写的原子快照；完整写入与快照例程保持原样。
