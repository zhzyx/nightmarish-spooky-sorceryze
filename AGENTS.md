# AGENTS：项目约定根导航

本文件只负责任务分类与文档定位，不直接堆积各领域的具体规则。

## 加载规则

1. 根据当前任务在下表中选择模块，只读取命中的模块，不必加载全部文档。
2. 先读模块的 `README.md`，再按模块索引进入与任务相关的子模块。
3. 子模块可以继续拆分；只沿当前任务所需的路径向下读取。
4. 同一事项存在多处约定时，以更具体的子模块为准，并及时修正重复或过时的描述。
5. 下文路径均相对于项目根目录。

## 模块路由

| 任务类型 | 模块入口 |
| --- | --- |
| 工单、验收、分支清理、规范维护与路由迭代 | `Markdown/workflow/README.md` |
| 编译、安装、启动、构建边界与构建契约 | `Markdown/build/README.md` |
| 测试选择、回归验证、验收证据与结果记录 | `Markdown/testing/README.md` |
| C++ 命名、格式、API、内存、并发与代码评审 | `Markdown/code-style/README.md` |
| UI 输入命令化、编辑器语义操作、外部 CLI／HTTP 接入 | `Markdown/editor-control/README.md` |
| Gameplay 对象、生命周期、会话、专服、复制、相关性与预测 | `Markdown/gameplay/README.md` |
| EngineCore 核心架构、公共契约、引擎适配与迁移边界 | `Markdown/engine-core/README.md` |
| 查找原始规范、项目记忆、需求设计与历史验收资料 | `Markdown/sources/README.md` |

## 扩展约定

- 每个模块使用独立文件夹，并以 `README.md` 作为模块索引。
- 子模块使用自己的文件夹和 `README.md`，由父模块索引负责导航。
- 新增规范必须先并入现有最匹配的细则；确属新领域时才新增模块并登记。
- 模块颗粒度过碎、职责重叠或总是共同加载时，必须合并并同步修正路由。
- 新增、拆分与合并的完整流程见 `Markdown/workflow/documentation/README.md`。
- 具体规则只保留在负责它的模块中，根文件和父模块不复制正文。
