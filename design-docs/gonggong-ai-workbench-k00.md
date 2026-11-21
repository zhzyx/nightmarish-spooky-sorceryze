# K00　基础接口与归属验收

七张 M0 输入首次齐备于 B06 合入后的主线提交 `ab02c5451b8e966b0b0408f776e21c836051ac2f`。本表以这棵树为共同基线。每行的清单给出产品源码与调用入口，验收评论绑定各自的交付修订。七张原单均已按 completed 关闭。[K00 原单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1718) · [共同基线](https://github.com/zhzyx/nightmarish-spooky-sorceryze/tree/ab02c5451b8e966b0b0408f776e21c836051ac2f) · [定向复验与完整对象号](../data-collection/gonggong-ai-workbench-plan1-k00.json)

| 生产卡与目标验收回执 | 产品生产者、输出与实际读取者 | 方案一直接接收卡 | 后续验收责任 |
| --- | --- | --- | --- |
| [B01 入口清单](gonggong-ai-workbench-b01.md) · [#1873 验收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1873#issuecomment-7053338737) | EditorNode 注册主屏和插件，编辑器通过布局键恢复页面。AI Chat、天枢、3D 面板及马良有各自的挂载点和打开动作。 | B05、B06、B07 | U01–U06、U13/U14 在新工作台验证唯一实例、焦点、深链和旧布局。Q01、Q10、Q11 复验实际窗口交互。 |
| [B02 能力矩阵](gonggong-ai-workbench-b02.md) · [#1870 验收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1870#issuecomment-7053450184) | 天璇域服务产出带身份和版本的工单、文档、会话与判断记录，由 Web 和已有原生调用点读取；原生需求执行服务按授权向偃师派发规划。39 项矩阵逐项给出接口或缺口。 | B05、B07、C01、D14、I12 | I、D、H 系列按矩阵验收各自的原生产品调用和权限。已有 155 项服务用例的范围见原单。 |
| [B03 执行路径](gonggong-ai-workbench-b03.md) · [#1874 验收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1874#issuecomment-7053477649) | 天枢画布绑定工单后交司南判断；用户开工后，本机聊天桥启动工作者，控制器按执行 token 将终态送回原工单。退出码 7 的原回执为 `reconcile_required`。 | B06、B07、D01 | R01–R09 验收检查点、进程终态与恢复。Q04/Q05 在同一候选上分别实测 Windows 和 macOS 重开。 |
| [B04 历史标识](gonggong-ai-workbench-b04.md) · [#1853 验收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1853#issuecomment-7053314565) | 原仓提供 Git 标签和提交，多宝 GitService 导入镜像；原生迁移目录以来源键、归档修订和对象键供历史详情回读。Git OID 与原生修订均有定位。 | B07、G01、G02 | G05 覆盖全量标签。G16、G23/G24 核销存量 PR。G20–G22 负责正式切换。 |
| [B05 隔离样例](gonggong-ai-workbench-b05.md) · [#1827 验收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1827#issuecomment-7058017416) | 装载器通过天璇建立两名用户、各自的模块需求及同名工单；移动和动画模块各用多宝 compose 固定共享模型版本，再用 read 读取 GLB。 | C03、K00 | C03 验收资产显式关联、打开及独立解绑；K01 使用此样例验收现场入口、返回视口和跨模块草稿隔离。 |
| [B06 构建与回退](gonggong-ai-workbench-b06.md) · [#1872 验收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1872#issuecomment-7058041829) | SCons 编译原生外壳与内嵌输入。桌面加载器按路径、兼容版本和摘要选择 UI 包；AI Chat 从安装根选择 Python 桥。B06 记录了 Windows 同一二进制下 48→96→48 的切包与回退。 | K00、U01 | U01 修改原生命令后重建对应平台并验证；新平台或二进制需分别验证包选择与回退。 |
| [B07 来源映射](gonggong-ai-workbench-b07.md) · [#1719 验收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1719#issuecomment-7057504758) | 基线表将旧设计、四张起始卡的已接收候选和 164 卡索引关联到退出、旧 UI、工单权威源及存量 PR 的责任卡。GitHub 记录本批实际签发。 | K00 | R/Q 系列验收关停与重开；I01/I02 验收天璇原生编号；G16、G23/G24 按原评审、精确候选和最终处置逐条核销。 |

## 在共同基线上复验

1. 对每张输入，回读原单的完成原因、独立验收评论和目标为 main 的已合入 PR。用 `git merge-base --is-ancestor <合入修订> ab02c5451b8e966b0b0408f776e21c836051ac2f` 核对归属，并用 `git rev-parse <修订>:<仓库相对路径>` 对照每张卡在其合入树及共同基线中的设计、证据和 B05 样例文件。各组对象号见主证据的 `inputs`。
2. 从仓库根运行 `python -B -X utf8 samples/gonggong-workbench/fixtures/b05/sample.py`。本次连续三轮重建，移动、动画的同名工单保持各自归属；两次重置均清除批注。两个消费者共六次读取的 GLB 摘要均为 `732a267f0e06004a2e3780a58834e22ab6ab45b577a75c5d95744225559ea2d2`。
3. 从原仓读取标签 `gonggong-windows-x64-20261104-r2`，核对 B04 记录的提交、树及父链。在多宝兼容层的临时库复验镜像保留分支与标签、快进、冲突后保留目标和标签增删，四项均通过。原生归档的对象键及 B06 同二进制回退沿用各自已接收的实测回执。

[K01](gonggong-ai-workbench-plan1.md#k01) 从 B01 查到现场入口并以 B05 样例检查模块归属。[K06](gonggong-ai-workbench-plan1.md#k06) 从 B04 取得标识边界、从 B07 取得原始 PR 处置责任。各自开工还需按原卡回读其他直接前置的验收。
