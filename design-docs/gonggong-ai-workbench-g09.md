# G09　在 Godot 内回看多宝历史

在天枢主屏选择「多宝历史」，填写归档项目。填写仓库相对路径后查询可显示修改过该文件的提交。选中一行可阅读该提交中的文件内容，点击「查看原始提交」可核对来源标识、提交者、树对象和归档版本。留空路径可直接浏览提交。每次查询固定一份已发布的天璇目录，后续翻页和选中的提交都沿用该版本。[G09 工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1780)

Windows 验收从真实 Git 仓库导入一个中文路径文件的两次修改，在隔离的 headless 编辑器中打开原生控件，依次选择两个修订并核对文件和来源。过期目录版本和不存在的文件分别触发读取失败。[原生探针](../tests/editor/daqian_archive_history.gd) · [验证结果](../data-collection/gonggong-ai-workbench-plan1-g09.json)
