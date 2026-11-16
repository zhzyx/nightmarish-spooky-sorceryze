<!-- gonggong-request:engine-next-network-gpu-warmup-20261117 -->

# 可视客户端冷启动握手

本单关联 #1343 与父单 #1323。最终局部阴影候选 d1ef50f207a061a8d08ed72d71b84aad58157a9ba14f686ce9acf774e8b55661 在双可视客户端 GPU Validation 冷启动时失败。

## 已观察事实

final3-r3 的客户端 A 首帧耗时约 83 秒，随后报告 Network visual client step 失败。A 未收到 Welcome，B 已连接。LoadScene 创建 ClientSession 后才进入 GPU 资源和管线初始化，首次网络 Tick 与后续 Tick 之间也可能发生首帧 GPU 编译等待。

## 修复

保留原 SceneDocument 加载与资产摘要核对，在首帧成功提交且 GPU 退休后启动 ClientSession。从下一循环开始按既有固定步长路径驱动网络。记录实际会话启动状态和失败返回值。

## 验收

- 验证网络初始化发生在首帧 GPU 完成之后。
- 冷启动双客户端真实连接成功，WASD 输入、重连和最小化期间网络继续推进。
- 继续通过原 M2/M3 运行时回归和视觉 GPU Validation。
- 新候选通过精确 CI 并回读 main 后关闭本单。
