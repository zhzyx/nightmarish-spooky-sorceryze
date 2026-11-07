# 天枢 AI 真实链路排障

稳定需求 ID：tianshu-live-ai-path。原工单 [#515](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/515)。用户反馈既有模拟验收不能证明编辑器可用，怀疑死锁或鉴权失败。

在已安装的 Windows 编辑器从画布发出只读问题，经当前账号、已保存的模型连接，核对模型子进程、答复及画布回显。在天枢创建独立测试工单 [#516](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/516)，用编辑器的真实模型判断核对其路由结果。需求原文和专用验收范围见 [测试工单来源](daqian-direct-355dd3a992b5e7be89e2.md)。不把离线用例、工单创建、模型选择或仓库权限当作推理成功。

已复现的界面缺陷是等待真实答复时看板同步覆盖“正在分析”。等待和终态反馈应跟随当前画布请求，切换范围后保持隔离。独立 CLI 的传输诊断、编辑器回显和其他 AI 节点的验收分别记录。
