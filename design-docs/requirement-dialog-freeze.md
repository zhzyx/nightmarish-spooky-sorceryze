# 天枢创建需求时的编辑器响应

关联工单 [#497](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/497)，需求 ID 为 requirement-dialog-freeze。用户报告打开需求界面后卡顿，确认创建时失去响应。

验证 Windows 编辑器在进度监听子进程退出后停止读取断管，详情页处理刷新时保留隐藏总览节点，返回时显示最新工单。通过隔离的创建场景验证原草稿、重复点击、建单结果不明确后的核对，以及建单后的模型判断。截图所示需求已绑定 #494，应复用原工单。
