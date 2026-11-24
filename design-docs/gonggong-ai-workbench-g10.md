# G10 在 Godot 创建和切换多宝分支

天枢工具栏的「多宝分支」读取当前打开的 Godot 项目所在的 Git 工作副本，显示其根目录、分支和完整提交。用户选择多宝仓库，填写分支名和明确的基线提交后，控件使用现有认证服务创建分支，再从服务端读取完整分支引用的实际 tip。工作区尚未绑定共工时也能从工具栏打开。[原工单](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1844) · [设计总单](gonggong-ai-workbench-plan1.md#g10)

切换前检查已显示的本地分支和提交、目标分支的服务端提交、本地对象、当前工程在目标修订中的路径及编辑器内未保存状态。用户可取消，或显式选择保存脚本、场景及保全本地文件。保全使用 Git stash，包括未跟踪文件。复核保全记录后才允许切换。回到原分支与原提交，用户可根据界面显示的记录逐份恢复。恢复后读取真实文件及暂存状态；工作台保留原 Git 备份并标记已恢复的记录。

## 宿主接入与回退

原生对话框和工作区脚本随编辑器编译。已安装宿主目录提供工作副本工具和天璇桥接脚本，沿用工作流 Python 设置。服务端新增的只读分支 tip 接口按准确引用读取，保留现有分支创建接口及其权限检查。回退时可使用原先验证的编辑器和配套宿主，已创建的 Git 分支及 stash 继续留在各自仓库。

## 验证

运行入口为 `tests/editor/run_workbench_duobao_branches.py --godot <候选编辑器> --report <回执>`。一次隔离测试启动两次编译后的编辑器，使用真实登录会话、回环天璇服务、裸库和项目工作副本。独立读取服务端引用、本地 HEAD、未保存的脚本和未跟踪文件。另有四项真实 Git 仓回归，覆盖多份保全、同名标签、缺少项目及恢复冲突重试。[验收记录](../data-collection/gonggong-ai-workbench-plan1-g10.json) · [原生探针](../tests/editor/workbench_duobao_branches.gd) · [工作副本回归](../customizations/components/tianxuan/server/test_branch_workspace.py)
