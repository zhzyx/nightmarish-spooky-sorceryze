# SkinTokens 本地自动绑骨管线（独立配置，可整体回退）

在马良现有「解剖模板拟合」之外新增的**第三条绑骨路线**：用本地开源模型
SkinTokens/TokenRig 直接从静态 GLB 生成骨架与蒙皮权重。全程**无云端服务、
无 Blender、无 Python ML 环境**（推理在 C++/GGML 可执行文件内完成）。
现有 `standard` / `free` 路线、ComfyUI/Kimi/motion 各管线不受影响。

学习式绑骨对训练分布内的体型效果最好；输出**未经人工验收**（
`quality=learned_auto_rig_not_reviewed`），保存前必须在预览中检查骨骼与变形。
本管线的合成单元测试证明适配器行为，不证明真实推理质量。

## 组成与边界

| 位置 | 作用 |
| --- | --- |
| `tools/skintokens.cpp/` | 固定上游源码快照（localai-org/skin-tokens.cpp，commit `43aac7b0`）；GGML 作为本机固定版本构建依赖，不嵌入 Git 元数据 |
| `tools/ainative/skintokens_rig.py` | 独立配置管线：配置校验、GLB 校验、调用 CLI、provenance。标准库实现 |
| `tools/ainative/skintokens-config.example.json` | 本机配置模板 |
| `tools/ainative/test_skintokens_rig.py` | 合成 CLI 契约测试（9 项） |
| `samples/ainative-workbench/addons/ainative/skintokens_route.gd` | Workbench 新路线：调管线、导入结果、独立 stage |
| `samples/ainative-workbench/addons/ainative/rigging_panel.gd` | 唯一改动的共享文件：第三路线选项及显式分支 |
| `samples/ainative-workbench/skintokens_route_acceptance.gd` | Godot 侧契约检查 |

所有生成物（构建环境、编译产物、权重、运行输出）都在本机 `runtime/skintokens/`，
已通过 `.git/info/exclude` 的 `/runtime/` 本地排除，不进版本库。

## 构建（macOS 实测，CPU）

```bash
# 独立构建工具环境（不动系统 Python/Homebrew）
python3 -m venv runtime/skintokens/build-venv
runtime/skintokens/build-venv/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple cmake ninja
export PATH="$PWD/runtime/skintokens/build-venv/bin:$PATH"

# nlohmann-json（find_package 需要标准安装）
git clone --depth 1 --branch v3.11.3 https://github.com/nlohmann/json.git runtime/skintokens/nlohmann-json
cmake -S runtime/skintokens/nlohmann-json -B runtime/skintokens/nlohmann-json-build \
  -G Ninja -DJSON_BuildTests=OFF -DCMAKE_INSTALL_PREFIX="$PWD/runtime/skintokens/prefix"
cmake --build runtime/skintokens/nlohmann-json-build --target install

# GGML 固定到上游锁定的 commit，构建依赖留在本机 runtime
# 源码：https://github.com/ggml-org/ggml
git clone https://github.com/ggml-org/ggml runtime/skintokens/ggml
git -C runtime/skintokens/ggml checkout 8c63e70982c95ceb862e3a1073a2c1beef75d60a
cmake -S tools/skintokens.cpp -B runtime/skintokens/build -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DSKINTOKENS_ENABLE_VULKAN=OFF \
  -DSKINTOKENS_GGML_SOURCE_DIR="$PWD/runtime/skintokens/ggml" \
  -DCMAKE_PREFIX_PATH="$PWD/runtime/skintokens/prefix"
cmake --build runtime/skintokens/build -j 8
# 产物：runtime/skintokens/build/bin/skintokens-cli
```

## 权重（约 1.25 GB，仅首次需要）

```bash
runtime/skintokens/build-venv/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "huggingface_hub[hf_xet]"
runtime/skintokens/build-venv/bin/hf download LocalAI-io/SkinTokens-GGUF \
  --include "F16/*" --local-dir runtime/skintokens/models/SkinTokens-GGUF
```

权重只读保存在本机；上游 checkpoint 为 MIT。网络受限时这一步可能很慢，
管线其余部分（编译、合成测试、Workbench 配置检查）不依赖权重。

## 配置与使用

复制 `tools/ainative/skintokens-config.example.json` 到本机位置，填入
`skintokens-cli` 与权重目录的绝对路径。`device` 支持 `cpu`（默认）/
`vulkan`/`auto`；`postprocess=true` 启用上游表面局部性启发式；
`fingerprint_weights` 控制是否在报告中计算权重 SHA-256。

CLI（源文件永不修改，输出与报告必须是新文件，失败不自动重试）：

```bash
python3 tools/ainative/skintokens_rig.py --config /path/to/config.json \
  --source character.glb --output runtime/skintokens/character-rigged.glb \
  --report runtime/skintokens/character-rigged.json
```

Workbench：带 `AINATIVE_SKINTOKENS_CONFIG=/path/to/config.json` 环境变量启动
编辑器，在「角色骨骼绑定」面板选择 **SkinTokens 本地自动绑定 · 实验（独立管线）**，
载入网格后点「拟合并预览清理结果」。未配置时给出明确提示，不影响其它路线。
结果带 Skeleton3D，可直接预览并「保存角色新版本」（复用 `rigging_publish.py`
原子发布）。若面板包含统一的头脸验收门禁（`head_review`），SkinTokens 路线与
模板路线一样先通过该门禁再执行绑定——这是面板级前置契约，独立于本管线。
输出为静态绑定姿势，**没有**模板路线的内置 ROM 检查动画；
动画接入与变形验收在 Godot 动画系统中进行。

provenance 记录输入/输出 SHA-256、CLI 指纹、权重清单、设备、耗时及
`blender_used=false`、`cloud_used=false`、`fallback_used=false`。

## 验证

```bash
python3 -m unittest discover -s tools/ainative -p "test_skintokens_rig.py"
bin/godot.macos.editor.arm64 --headless --path samples/ainative-workbench \
  --check-only --script addons/ainative/skintokens_route.gd
bin/godot.macos.editor.arm64 --headless --path samples/ainative-workbench \
  -s skintokens_route_acceptance.gd
```

本次接入的实测状态（2026-11-17，macOS arm64）：

- 上游编译成功（CPU 构建，Vulkan 关闭），`ctest` 4/4 通过；
  `skintokens-cli glb-info` 已正确解析真实角色 GLB。
- 管线合成单测 9/9、Godot 契约检查通过；现有模板绑骨回归 `failures=[]`。
- 本机配置已生成：`runtime/skintokens/config.json`（CLI 路径已指向编译产物）。
- **未完成**：GGUF 权重因网络受限（各通道仅 KB/s 级）未能下载，
  真实推理验收待权重就位后执行；缺权重时管线按预期显式报错、不产出文件。
  权重下载完成后用上面 CLI 小节的一条命令即可验收真实绑骨效果。

## 回退

1. 不再选择面板第三路线即可停用；现有两条路线行为不变。
2. 彻底移除：删除上表中的新增文件，`git checkout -- samples/ainative-workbench/addons/ainative/rigging_panel.gd`
   还原面板，再删除本机 `runtime/skintokens/` 与 `tools/skintokens.cpp/`。
3. 已保存的 `.tscn` 角色版本与 GLB 产物是普通资产，回退后仍可打开使用。
