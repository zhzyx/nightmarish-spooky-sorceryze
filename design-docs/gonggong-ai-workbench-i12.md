# I12　从天枢打开历史工单原件

在天枢主屏选择 **历史工单**。输入归档项目、原始标识或 GitHub 工单链接，再选择 **读取历史工单**。从单项工单的天璇弹窗打开时，输入框会带入该工单的原链接。[设计工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1790)

读取器使用当前天璇身份查询归档，在原生窗口显示标题、归档状态和完整正文。遇到无效链接或无权读取的归档时，窗口保留调用方输入的归档项目与原始标识，方便核对。部署需要配套版本的天枢原生界面和主机上的天璇桥接脚本。[桥接入口](../customizations/components/tianxuan/server/tianshu_bridge.py)

macOS 定向复验从 GitHub 只读取得旧单 #1642，在隔离归档中复现正式读取流程。成功与失效请求、工单前后状态及源码摘要见[原生验收记录](../data-collection/gonggong-ai-workbench-plan1-i12.json)。
