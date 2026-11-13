# Engine Next 构建契约

本契约用于逐步建立独立于 Godot 的新运行时，不允许通过改名、包装或间接包含继续依赖 Godot 对象模型。

## 核心边界

- 新引擎使用独立的 `engine_next/`、`runtime_next/` 源码根；Godot 兼容适配只能进入 legacy 目标。
- 公共接口不得暴露 Godot 类型；直接与传递本地包含都受源码门禁约束。
- 链接清单必须来自实际构建输入，并绑定对象、库、运行文件及其摘要。
- 静态检查不等于完整 C++ 语义分析、许可证审计、干净环境运行或无 Godot 符号证明。

## 当前检查入口

在包含这些工具的实际仓库根目录运行：

```sh
python3 -m unittest tools.test_check_engine_next_contract -v
python3 tools/check_engine_next_contract.py --repo .
```

空源码树返回 `no_sources`，不得描述为“已验证无 Godot 运行时”。要求真实源码时使用 `--require-sources`；真实链接目标还需按当前契约提供实际链接清单，不能用未来命令冒称已执行。

## 权威资料

完整设计与验收边界见 [Engine Next 无 Godot 构建契约](../../../design-docs/engine-next-build-contract-20261112.md)。机器可读契约与检查器分别位于 `tools/engine_next_contract.json`、`tools/check_engine_next_contract.py`。
