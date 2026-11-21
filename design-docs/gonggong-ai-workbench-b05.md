# B05　角色移动与角色动画的隔离样例

本样例供工作台在同一项目中区分两张标题均为“检查角色表现”的工单。两张单分别归属一个业务模块，由两名用户创建，并使用同一份 Suzanne 模型。入口是工作台样例目录中的清单和 Python 装载器，依赖仓库内的天璇领域服务、多宝版本库及已有 GLB。所有路径以仓库根为基准。[B05 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1827) · [上游入口 B01](gonggong-ai-workbench-b01.md) · [身份与接口 B02](gonggong-ai-workbench-b02.md) · [样例清单](../samples/gonggong-workbench/fixtures/b05/sample.json) · [装载器](../samples/gonggong-workbench/fixtures/b05/sample.py)

| 业务模块及稳定键 | 样例用户及角色 | 天璇工单 | 模块设置 |
| --- | --- | --- | --- |
| 角色移动 `character-movement` | `movement`，租户管理员 | #1 检查角色表现 | 移动速度 3 米/秒 |
| 角色动画 `character-animation` | `animation`，编辑者 | #2 检查角色表现 | 默认动作 `idle`，循环播放 |

天璇用每个模块的稳定键创建私有需求，再以该需求的 `id` 建单。按模块查找时传入需求 ID，打开工单时用当轮的工单 ID。管理员可列出租户工单，动画编辑者只能列出 #2，直接读取 #1 会返回 `PermissionDenied`。在 #2 追加批注后，#1 的批注列表仍为空。[天璇工单与权限](../customizations/components/tianxuan/server/tianxuan_core.py)

多宝的两个业务模块各有独立版本与 `settings.json`。两者的依赖指向同一个 `shared-character-model` 资产命名空间及同一个不可变版本。该版本仅保存一个对象 `models/suzanne.glb`，其来源是仓库测试模型。任一模块均可单独调用 `compose`，从返回的依赖表取得精确版本，再用 `read` 读回同一对象的字节。移动速度和动作名称是业务样例数据。[模型源文件](../tests/data/models/suzanne.glb) · [多宝版本及组合接口](../customizations/components/tianxuan/duobao/native_store.py)

## 重置与复验

从仓库根以 Python 3.11 或更高版本运行以下命令。装载器每次进入 `sample()` 都在独立临时目录中创建两个 SQLite 库，退出时关闭并清除。下游 Python 用例可以在同一 `with sample() as (domain, native, state)` 作用域内读取或更改样例，重新进入即可从清单还原。按 `state["modules"][模块键]` 查找当轮需求、工单、用户、编号及版本。

```powershell
py -B -X utf8 samples/gonggong-workbench/fixtures/b05/sample.py
```

Windows、Python 3.14.3 的实测以 `0e1dcb293a55e3034bf92b4e02bc6b0028e5fb14` 为源码基线。连续创建三轮样例，每轮验证两名用户的身份、两张同名工单的归属与访问、独立设置和模型字节，并写入临时批注。两次重置后批注均回到空列表，逻辑键、工单编号和资产版本一致，租户、用户和工单 ID 都重新分配。进程退出码为 0。验收回执保留实际的三轮身份及版本映射、两条消费者读回的模型摘要，以及清单与装载器的 SHA-256。[实测回执](../data-collection/gonggong-ai-workbench-plan1-b05.json)

## 接收位置

[C03 #1806](gonggong-ai-workbench-plan1.md#c03) 可沿两个模块的稳定键和共享资产版本，验证工作台显式关联、打开模型及独立解绑。[K00 #1718](gonggong-ai-workbench-plan1.md#k00) 可从同一份回执核对天璇建单与权限、多宝消费模型的来源与版本。原生控件的选中、打开及解绑交互由相应后继工单实测。
