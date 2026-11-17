# 马良图生网格支持单图与图片列表输入

<!-- gonggong-request:maliang-mesh-multi-image-input-20261117 -->

日期：2026-11-17（Asia/Shanghai）。路径基准：仓库根。

## 目标与授权

用户以实际“图像生成网格”节点截图指出输入仍为单一图像。当前对话明确要求修复该节点的输入能力。本工单只覆盖 `image_to_mesh` 的单图／图片列表输入、兼容验证及 main 交付。

## 范围

- 新建 `image_to_mesh` 节点使用版本 2，输入 `source` 同时接受 `image` 与有序 `image_set`，输出仍为单个 `mesh`。
- 本地源图和参考图允许多选并保持顺序；上游图片队列可以连接到同一输入端口，不能被静默压成首图。
- 适配层在调用既有版本 1 Provider 前，将 `image_set` 展开为主图＋有序参考图上下文；单图保持原路径，文字提示保持不变。
- 既有 Provider 的输入数量与图文能力边界保持真实：Kimi Native 直接三维最多 4 张，API 有机建模最多 2 张，旧原语建模仅 1 张；超限或不支持的图文约束必须明确报错，不能静默丢弃。
- 既有 `image_to_mesh` 版本 1 节点、工作流、任务恢复和其他节点契约不变。
- Godot 端口、文件选择、保存重开和协议适配增加回归；不把 Fake Provider 结果写成真实三维生成或视觉验收。

## 验收

- Python 覆盖单图、图片列表展开、顺序、文字保留、版本兼容和空输入拒绝。
- Godot 覆盖节点输入名称、图片队列连线、多文件选择及保存重开。
- 受影响 Python、Ruff、Godot 和原生内嵌包一致性检查通过；正式门禁、精确候选 CI 和远端 `main` 回读完成。

## 验收结果

- 生图相关 Python 共 87 项运行、19 项按平台或依赖跳过、0 失败；Ruff check 与 format check 通过。
- Godot 端口、图片列表连线、本地多选、保存重开、参数表单和节点菜单全部 `failures=0`；旧版 `image_to_mesh` 版本 1 仍保持单图输入。
- macOS arm64 编辑器重新生成内嵌资源并链接，SHA-256 为 `27e8599a0cb24e7d6d0b1c7e680e9ec39eab614607f7573e039f0d5e6da9eec0`。`run_ainative_builtin.py` 四个原生场景及源码／内嵌包一致性通过，新增图生网格多文件选择断言通过。退出阶段仍有既知 RID／ObjectDB 泄漏警告，本单不声称修复。
- 脱敏证据见 `data-collection/maliang-mesh-multi-image-input-20261117-validation.json`。本单验证输入和 Provider 适配，不声称完成真实三维生成或视觉质量验收。
