# 修复 macOS 与 Ubuntu CI 缺少 NumPy 依赖

<!-- gonggong-request:ci-numpy-macos-ubuntu-20261119 -->

日期：2026-11-19（Asia/Shanghai）。路径基准：仓库根。

## 问题与授权

用户在了解 Windows CI 通过而 macOS／Ubuntu CI 失败后，明确要求“修复一下吧 在这些环境下。当bug修”。本工单只修复 CI 测试环境的依赖声明，不改变业务代码或测试判定标准。

## 根因

`.github/workflows/engine_next_contract.yml` 的 `source-contract` 矩阵在 Windows、macOS 和 Ubuntu 上运行同一套 AINative Python 测试，但 `Install test dependencies` 只安装 Pillow。`test_geometry_repair.py` 无条件导入 NumPy，导致 macOS 与 Ubuntu 出现 `ModuleNotFoundError`；`test_kimi_direct_provider.py` 再导入该测试夹具时产生第二项错误。

## 修复范围

- 在共享的依赖安装步骤中固定安装 `numpy==2.4.4`，与本地完整回归通过的环境一致。
- 保留既有 Pillow 版本、Python 3.12、测试命令和 Windows 专用构建路径。
- 不跳过失败测试，不把依赖缺失伪装成通过。

## 验收

- 工作流 YAML 可解析，差异只包含 NumPy 依赖声明。
- 本地完整 AINative Python 回归通过。
- PR 的 macOS 与 Ubuntu `No Godot source or link dependencies` 作业不再出现 NumPy 缺失错误，并实际完成测试。
- Windows 作业保持通过；按 CI 工作流变更要求核对 Windows Editor 与原生回归、独立审查和远端 `main`。
