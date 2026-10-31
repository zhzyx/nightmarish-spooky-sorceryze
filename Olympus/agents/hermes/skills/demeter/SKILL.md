---
name: demeter
description: Classify Hermes data by actual generated Agent versions and associated work; isolate framework references.
---

读取 ../../references/optimization.md。以实际 Agent 快照为首要维度，再按需求、工作、问题、阶段及影响分组；复用版本化分类，允许多标签与未知。跨渠道同一事件归簇但保留来源。

默认归 feature/project/module/agent。只有跨 Agent 或通讯关联证据才可能标为 framework，且只形成 reference；宙斯也只形成 reference，等待用户单独指令。关联标注明确 confirmed/possible/unknown，不能把可能关系算成已证实根因。分类记录保留理由、目标快照及依据，交 mnemosyne。

按随附 reporting.json 使用奥林匹斯共享赫尔墨斯上报入口；运行须由宿主绑定实际需求与数据源，排队不等于落库成功。
