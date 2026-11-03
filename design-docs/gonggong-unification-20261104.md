# 共工统一迁移

工单：https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/43
需求 ID：gonggong-unification-20261104。基线：8bdb8c02ebbbfdcc40dcda95dfc4a5b89d1eaf18。

用户要求将当前共工框架完整合入现有 Git 仓库，取消 Olympus 及双框架同步，保留 Godot/Git 接入与完整历史，交付 main、Windows x64 编辑器及完整下载包。最终唯一主工作区使用共工名称，框架根为 framework/。

实现分支先准备候选，保留旧框架原件及历史事件。现行 Agent/工具/配置/界面统一共工；旧工单 marker 和旧数据仅作显式历史读取。采集新旧租户隔离，不重写来源、批准、摘要或历史事件。

验收包括完整性与正式准入、无旧来源独立运行、工单与采集、权限拒绝、Godot 模拟链路、Windows 构建、解包运行、远端 main/发布回读及工作区关联修复。验证绑定同一候选；准入和发布尚未完成前保持既有运行入口。

当前状态：隔离候选实施中。五个 Agent 的精确候选已获用户批准并通过正式核验；工作区切换、main 合入及新包发布仍待完成。实际事件由当前宿主采集，不声称全量监听或供应商用量可用。
