# A05 从已验证的产物续授下一阶段

工单负责人可以在预览通过后留在当前阶段，随时按原票据查看产物，也可以指定下一个目标并确认续授。天璇保留每个阶段独立的执行票据、候选、模块版本、判断人和检查结果。[A05 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1762)

## 从预览继续

1. 在 `POST /api/v1/native/workflow/status` 提交预览票据 `key`。确认 `stage_result.state` 为 `stage-reached`，按 `candidate` 和 `modules` 查看检查过的产物。此时重新驱动司南也能保持原产物可查看。[A04 的阶段检查](gonggong-ai-workbench-a04.md)
2. 在原工单的阶段目标中填写下一阶段及到达标准，使用「逐项确认启动」签认这一项。工单详情中的 `task_confirmation` 返回新目标的 `target_revision`、本次确认的 `revision` 和判断人 `confirmed_by`。工作流继续沿原工单 ID、定义修订及拆单时的设计版本核对签认。[A02 的逐项确认](gonggong-ai-workbench-a02.md)
3. 由该负责人向 `POST /api/v1/native/workflow/renew-stage` 提交原票据和刚确认的两个修订号。例如：

   ```json
   {"key":"<已达阶段的执行票据>","target_revision":2,"confirmation_revision":2}
   ```

   回执中的 `task` 是下一阶段的新票据，`from` 包含前一阶段的完整检查回执，`authorization` 保存新的阶段名称、到达标准、负责人和签认修订。用新票据查询 `status.stage_renewal` 可读回这次决定。两次并发提交相同续授或服务重开后重投，可取得同一张新票据。签认过期、阶段未达、原检查证据撤销或工单定义改变时，服务会拒绝新续授。原票据仍可按原读取权限查看。
4. 沿原有司南驱动继续新阶段。宿主从已安装计划取得生产工具、写入范围、检查和其他输入；与前一阶段重叠的模块使用上一回执中实际达标的修订。新阶段安装计划的 `stage` 和 `stage_criteria` 须逐项匹配新签认。续授继续采用原工单能力标签约束预约。[S01 的能力匹配](gonggong-ai-workbench-s01.md)

## 实测

从仓库根在已安装天璇测试依赖和 Node 的环境运行：

```powershell
python -m pytest -q customizations/components/tianxuan/sinan-workorders/test_native_stage_renewal.py
```

测试从认证天璇服务启动实际司南驱动和预览进程。第一阶段生成并检查蓝色圆形 SVG。下一阶段仅可写入 `package.sha256`，实际打开前一修订中的 SVG，写入其 SHA-256，再由另一进程验证文件内容。回执包含两次进程结束记录、原工单身份、检查过的候选、两阶段的模块修订、未续授时的调度、重复续授和重启后的调度。[定向用例](../customizations/components/tianxuan/sinan-workorders/test_native_stage_renewal.py) · [Windows 候选与接收回执](../data-collection/gonggong-ai-workbench-plan1-a05.json)

此变更位于天璇服务与本机工作流适配器。服务沿用现有任务、修订与阶段检查表保存回执，更新通过重新加载服务生效。Windows 实测覆盖 HTTP 到本机进程的路径；跨设备记录中 A02、A04 的主线接收修订分别为 `c38ec442392f230ec9e697730d21ab039026f9e0` 和 `7396689ea90635f9f576f277e2f2b9adfd5a0b52`。[A02 接收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1847#issuecomment-7073851176) · [A04 接收](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1841#issuecomment-7074386759) · [A05 执行归属](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1762#issuecomment-7074414946)
