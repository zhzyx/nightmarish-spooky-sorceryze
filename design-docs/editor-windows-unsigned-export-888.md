# Windows 未签名导出默认选项 (#888)

来源：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/888 。父项 #773，故障链 #807。当前变更只处理编辑器原生 `project_export` 的凭据边界和验收，不新增模块，不改变平台签名工具。

## 现象与边界

main93006dd2 的实际 Windows 模板导出在确认前被 `credential_export_not_supported` 拒绝。内置 Windows 平台默认关闭签名，却仍有 `codesign/timestamp=true` 与 `codesign/digest_algorithm=1`；原通用判定误把这两个非秘密选项作为凭据。

在既有无脚本、无 GDExtension 的平台检查之后，仅精确内置类 `EditorExportPlatformWindows` 采用逐项类型校验。`enable` 必须为 bool false；时间戳必须 bool；摘要算法必须整数 0/1。identity_type 必须整数 0；identity/password/timestamp_server_url/description 必须空字符串；custom_options 必须空 PackedStringArray。未知签名键一律拒绝。其他平台继续原规则，加密拒绝保持不变。签名设置仍进入预设内容摘要，预设文件与项目输入继续绑定确认；不修改预设以绕过拒绝。

该文件为原生构建输入；必须重编编辑器。无需重编同版本既有 Windows debug 模板。回退方式为回退本补丁并重编编辑器，原先保守拒绝恢复。

## 验收

`tests/editor/run_editor_scene_completion.py` 增加 `--windows-template`，复制模板进入隔离项目。正例保留默认 timestamp/digest，原生确认后输出 PCK 与真实 Windows EXE；检查 EXE/PCK 文件头和摘要，并仅复制 EXE/PCK 到源项目之外的独立目录实际运行应用。只有标准输出出现应用自身 marker、无 ERROR、退出 0 才通过。模板缺失必须返回实际失败。

反例覆盖签名开启、身份/密码/证书存储、非空自定义参数、加密、enable/timestamp/digest/identity/options 错误类型与摘要范围、确认后预设漂移。原有 macOS 空集合/非空集合与场景、资源、导入、ZIP、PCK 回归仍执行。未提供 macOS 原生模板时不声称 macOS 应用验收。

隔离编辑器在失败路径也先发送 fixture finish 再兜底 terminate；临时清理不覆盖业务失败。日志按 UTF-8 替换无效字节读取，防止 Windows 系统默认 GBK 掩盖验证结果。首轮原始失败报告保留，后续使用不同报告路径。

## 方法召回与证据

按 `framework/specs/method-learning.md` 召回租户 gonggong-workspace 的 godot-build-placement，trace-native-consumer revision14 为 verified。其“按实际原生消费者确认输入”的条件适用；资源包热替换或其他平台证据不代替本次原生重编与 Windows 应用实测。

本机验证证据均以本隔离工作树为解析基准，位于忽略目录 `bin/888-validation/`；正式发布由根会话归档可共享摘要与门禁证据。初次运行已取得应用 marker，但日志 GBK 解码造成总报告失败，保留 `scene-windows.json`；复验另存 `scene-windows-final.json`；加强源项目隔离后的首轮为 `scene-windows-isolated.json`（超时），`scene-windows-isolated2.json` 显示原始文件存在断言忽略原生资源重映射；改为实际加载 Gradient 后，最终 `scene-windows-isolated3.json` 通过。原主线失败保留在原责任者 private receipts，不覆写。

最终本机结果：严格 editor 构建成功；原生 SceneActions/TaskAuthorization 为 9 tests、125 assertions 全通过；scene-windows-isolated3.json 为 ok=true，独立目录的 EXE/PCK 成功加载导出 Gradient，输出 SCENE_COMPLETION_EXPORTED_APPLICATION_OK、stderr 为空、退出 0。ruff/mypy 与差异空白检查通过。
