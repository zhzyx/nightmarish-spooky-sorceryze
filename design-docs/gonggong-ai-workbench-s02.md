# S02　匹配当前本机的模型与 Agent

天璇把 S01 已签认的工单能力交给司南。打开认证的原生工作流看板，`inspect.environment.catalog` 会给出每个受信 profile 的能力、目标、配置状态和本次本机观察。生产角色模板提供 `agent`，模板绑定的提供方型号是 `requestedModel`。安装时已评估的 `capabilities` 决定这个组合可以承接哪些工单。[S02 原单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1848) · [S01 能力来源](gonggong-ai-workbench-s01.md)

## 从签认到预约

授权入口读取安装计划、工单能力和本地目录。显式指定的 profile 保留原绑定。自动选择优先取覆盖计划和工单全部能力、可用于 Agent 且当前可用的 profile，同等匹配按宿主 preference 和安装顺序取值。只有凭据缺失的匹配项时，签认仍可保留该票据，司南在 `deferred` 回显 `requiredCapabilities`、`missingCapabilities` 和 `localStatus`。[安装计划](../customizations/components/tianxuan/server/native_entry_factory.py) · [原生派发](../customizations/components/tianxuan/sinan-workorders/native_dispatch.mjs)

生产角色宿主在原操作系统身份下核验已安装程序，读取其固定环境。Codex 源按原安装摘要核实程序，调用 CLI 的 `login status` 与 `debug models`，匹配可见型号。CLI 明确报告未登录时回报 `credential_missing`。当前 CLI 无法提供型号清单时回报 `catalog_unconfirmed`，已不在可见清单的绑定回报 `model_missing`。本机 proposal Agent 核查已固定的程序、TLS 凭据、回环连接和对端证书摘要。独立角色服务通过原有双向 TLS 把结果传回天璇。普通本地命令沿工作者安装表核对可执行文件；远端节点沿已有节点宿主核验。看板与回执只投影 Agent、申请型号、能力和状态。[本机观察](../customizations/components/tianxuan/sinan-workorders/native_local_profiles.py) · [角色服务](../customizations/components/tianxuan/sinan-workorders/native_role_service.py)

预约与启动前会重新读取生产角色的本机状态。凭据在两者之间被撤回时，本机票据退回可派发状态并释放预约，工作者尚未启动。恢复凭据后可沿同一张票据重新匹配。已预约选择从服务端回读；物理工作者由原执行入口启动。各次模型推理与用量仍由模型调用回执证明。[原生工作流](../customizations/components/tianxuan/sinan-workorders/native_workflow.py)

## 接收、复跑与部署

Windows 实测覆盖两个签认工单，样例能力分别为 `coding` 和 `animation`。两个安装 profile 各命中所属能力并各完成一个确定性工作者进程。动画凭据撤回期间，缺口回执保留了要求的能力和具体登录状态，物理执行次数保持为零。同一套本机 Codex 另行回读实际登录状态和可见型号，并通过认证看板匹配其中两个型号；这一项执行的是能力发现。独立 TLS 接收测试核实生产角色读自己的有效环境，应用会话里存在的凭据也不能代替它。结果附确切源码 blob、选择理由、票据与产物修订。[定向用例](../customizations/components/tianxuan/sinan-workorders/test_native_local_profiles.py) · [接收回执](../data-collection/gonggong-ai-workbench-plan1-s02.json)

从仓库根、已安装天璇依赖及 Node 的环境执行以下命令。实机登录子用例需要可直接运行的 Codex CLI；目录中有两个可见型号时会执行双型号实机匹配。

```powershell
python -m pytest -q customizations/components/tianxuan/sinan-workorders/test_native_local_profiles.py
```

本次改动由天璇 Python 服务与 Node 派发适配器加载。生产安装继续固定 `native_*.py`、派发文件和角色服务源码树。更新时按现有流程重新准入对应版本并重启服务；回退时恢复原安装清单和配套宿主版本。实测在同一 Python、Node 二进制上替换已固定的样例 CLI 字节，目录转为 `installation_unconfirmed`，恢复原字节后重新返回原可用项。原生编辑器编译输入由现有构建链决定，本卡未改动该链。[安装约定](../customizations/components/tianxuan/server/native-entry-interface.md)
