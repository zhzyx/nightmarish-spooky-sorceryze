# 天枢入口星空简笔图标

来源：[Issue #494](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/494)，需求 ID `daqian-direct-9196000e1a2d3352e6a1`；原始需求：“给当前引擎的天枢前面的icon换成一个梵高的星空画作简笔”。来源为 Godot 大千草稿 `draft_9196000e1a2d3352e6a1`。本次执行授权引用 `user-chat-20261108-continue-Sail-Li-open-issues`，由当前 Codex 父会话委托，父会话负责独立审查与发布。

产物与边界：沿用 Godot 编辑器现有 SVG 图标编译及主题体系，新增 `editor/icons/StarryNight.svg`，天枢 `create_daqian_dock()` 从 `GraphEdit` 改为引用 `StarryNight`。用深蓝夜空、蓝色旋涡、金黄月星和前景柏树呈现《星空》简笔意象；16×16 画布保持与现有图标相同的布局尺寸，避免引入位图、字体或外部素材依赖。独立资源名避免改变其他使用 GraphEdit 的界面。

平台及验证：Windows 静默执行 SVG 语法、图标注册与实际 C++ 入口引用核对；在 16/24/32 像素及明暗背景检查轮廓可读性。固定画面色值不命中编辑器主题换色表，保留深蓝画框与金黄月星；不新增主题例外或引擎逻辑。纯 SVG 与单一引用改动不重编整套引擎，验证范围与限制在 `data-collection/issue494-starry-night-validation.json` 留证。仓库内相对路径均以仓库根为解析基准。

验收与停止条件：天枢入口唯一引用新资源、SVG 可解析和实际栅格化、标准尺寸及主题背景预览可读，设计、真实验证记录及谛听事件随完整候选交由父会话审查。远端 main 包含关系与 Issue 整体验收由发布者回读，本地候选不代表业务验收或已交付。
