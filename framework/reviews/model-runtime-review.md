# 獬豸·框架审查：跨模型本地运行层

临时独立运行验证职能，受元衡控制。结论：**本地合成运行复核通过**。这不是批准通行证，也不证明真实模型适配或生产部署已完成。

## 范围与方法

按共工 gonggong-check 回查冻结纲领与元衡标准，只读审查 runtime/runner.py、adapters.py、diting.py；参考 model-runtime 规范。自行在 work/model-review 构造模拟输入、崩溃夹点和实际 SQLite 断言，未修改输出框架实现。

运行器测试明确替换 context 为合成准入上下文、call 为可控模拟模型；HMAC签名、事件/状态库、锁、实际共用 reporter/outbox/谛听落库均执行。适配器测试只替换 urllib opener，独立验证响应解析与协议请求内容。没有访问外部服务或产生费用。

## 证据

最终运行验证 **29/29**，适配器独立验证 **11/11**。脚本分别为 work/model-review/probe.py、adapters_probe.py；原始结果 revision4/results.json、adapters-revision3/results.json。

覆盖委托篡改、过期、状态目录绑定、synthetic拒绝生产、任务类型路由、成功重放不调用模型、未知结果停止且必须操作员恢复、调用预算不重置、资源工具白名单、双worker锁、技能单次归属计量、质量问题和返工、完成和取消投影、持久结果/终态中断恢复、续期绑定和拒绝扩权。恢复夹点使旧已知输入10与新调用输入10全部落库，合计20。

适配器覆盖三类协议规范化、输出参数、systemless角色标签保留、拒绝外网明文HTTP和URL凭据、畸形消息/用量、负数和子集超过总量的未知结果处理。

## 发现及关闭

- MODEL-01：Repeated tasks collided on Agent snapshot logical identity。修复：Stable snapshot identifier, reuse immutable existing snapshot；独立反例与修复后验证均有记录。
- MODEL-02：Rejected model output was absent from quality evidence。修复：Durable validation outcome, quality_issue and later rework projections；独立反例与修复后验证均有记录。
- MODEL-03：Malformed nested responses escaped normalization; impossible usage poisoned projection。修复：Normalize malformed payload as TransportUnknown and reject inconsistent token subsets；独立反例与修复后验证均有记录。
- MODEL-04：Crash after persisted response silently omitted already measured usage。修复：validation_interrupted records unresolved response and retains measured consumption；独立反例与修复后验证均有记录。
- MODEL-05：Cancellation was not projected and terminal log/job status could contradict。修复：Durable termination projected; already completed/cancelled terminals only permit consistent delivery recovery；独立反例与修复后验证均有记录。
- MODEL-06：Expired grants could not be renewed for existing job reconciliation。修复：Signed renewal binds predecessor digest and compares complete scope excluding expiry/link; budget preserved；独立反例与修复后验证均有记录。

## 候选绑定

manifest SHA256：`25d0b069d116af1eaa236f7564e596c0c9fa41f8fddaa5d9d91aa3eab3ac268d`。

- runtime/runner.py：`b486dd8475b1365fc9dcfe4f3691804db994aa784e64ebc37901ffd09aeff51e`
- runtime/adapters.py：`8cf98e7004e9f0595c1e81de679aed5a7d1f69825154f866b51375b15255732f`
- runtime/diting.py：`17706f947f1d860d76ec81b07116bc93924ff7dd7054665f06ef7f6de170b0da`

- yanshi 0.4.0：`c40fe243a82ce1d850514919fa4da32644d17f3efae22e14026cba7d0d4f2f58`
- kuafu 0.4.0：`a5b184a3a1b652cf8b302fb9b97886a760620c79c64f376722cc1e2df5d5041c`
- diting 0.4.0：`ac953d822107a1f13c7aa18e8cb582ca5bc5ffd1fcfb5151eb7fa2ce20df0f07`

## 未验证与限制

真实定义准入集成由主任务另行测试，本报告的 context stub 不能作为定义准入证据。真实供应商身份、TLS/代理/网络异常、真实模型代表任务和语义能力、真实token计量、生产密钥隔离、企业IAM及高并发均未验证。当前结论仅说明合成条件下本地路径行为正确，不等同于这些模型已经适配成功。

元衡评价：Purpose对应授权生产任务；Truth区分模拟事实和真实能力；Economy复用共享运行器与谛听，不增常设Agent/skill；Authority模型仅提案、委托及工具范围受控；Adaptation以可复现故障推动修复；Continuity保留冻结纲领、原治理和质量责任链。报告保持可追溯证据和未知项，不声称无优化空间。

## 最终冻结核对

主任务确认冻结候选后，本审查再次独立核对 manifest 与三个运行文件SHA，重算三个Agent候选指纹，并运行 verify_framework.py candidate 完整性检查，均与上述绑定一致。审查结论仍只属于被绑定的本地实现。

另读取主任务 work/model-integration-results.json：10/10 合成HTTP协议、CLI、实际本地定义准入与上报集成检查通过，real_models_tested=false。这是主任务的补充证据，没有计入本审查独立执行的40项，也不被表述为真实模型验证。

## 发布前元数据差异复核

本次仅把 host_loader_implemented 标为 true 并限定 local_trusted_operator_runtime_only；reporting.runtime_deployed 保持 false，范围明确为 enterprise_or_external_host_deployment，另标 local_runtime_instrumented=true。撤销这四处增改并按原格式序列化，可精确重建前次 manifest SHA；三个运行文件与三个 Agent 指纹重新核对未变。该差异准确区分本地实现与外部生产部署，原40项运行证据继续适用，未重复无关测试。上方候选绑定已更新为发布前 manifest。
