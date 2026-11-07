# 降低天枢刷新频次

需求 ID 为 tianshu-refresh-rate，关联 [#505](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/505)。用户反馈天枢刷新过于频繁。

验收覆盖进度监听每两秒至多读取一次，进度通知、会话结束与重新打开页面引发的整板刷新合并且两次启动至少相隔十秒。没有事件时不发起后台刷新。手动刷新、建单后的回执处理、缩放交互与工作区切换的身份核对保持及时。
