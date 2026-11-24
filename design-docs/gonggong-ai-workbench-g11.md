# G11　从 Godot 提交所选文件

天枢工具栏的「多宝提交」打开当前项目的磁盘差异。用户点文件查看内容，勾选要提交的文件，填写说明并点「提交所选文件」。原生物化项目显示多宝模块和确切修订，G10 的 Git 兼容工作副本显示当前分支与 OID，并要求填写目标仓库。收到回执后，窗口显示接收修订和剩余改动。[原单 #1838](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1838) · [前置 G10](gonggong-ai-workbench-g10.md)

## 原生物化项目

工作流从打开项目的父目录定位物化来源，在当前认证租户读取模块及不可变修订，核对修订摘要。差异范围为该 Godot 工程目录，模块内工程目录以外的对象以及 Godot 本地缓存均保留。控件把所选路径和预览时的摘要交给宿主。新增、修改、删除均按对象处理。提交前重读选中文件，与预览摘要匹配后沿用天璇原生批次 API 的单文件 1 MiB、批次总内容 4 MiB 上限。绑定模块、基线、说明及精确路径摘要的请求键用于按操作者查询批次回执，服务端从已认证会话取得租户和操作者。回执未知时再次点击会先查同一请求键。宿主从返回修订校验父修订、对象集合及依赖；确认后在工程的 Godot 本地缓存保存差异基线。物化来源清单及工作文件保持原有字节。

## Git 兼容工作副本

差异预览从当前 HEAD 构造独立索引，按路径读取 Git 对象，可预览 64 KiB。提交以显示的基线与快照构造所选文件的树，首次发送前复查本地分支和所选内容。用户只勾选 A 时，传输中只包含 A 的变更。未选文件和原索引条目留在工作副本。对选中文件存在部分暂存的情况，也保留其显式暂存版本。一次请求可包含至多 1,024 个普通文件、链接或删除项，所传对象内容合计至多 16 MiB。子模块指针更新会报告原因。

接收端从已认证会话核对角色和分支保护，从基线和所选对象重建树，核验父提交及 OID，以旧 OID 为条件原子更新目标分支。工作副本以同一提交推进本地分支。候选引用存于本仓库的 `refs/gonggong/selected/`，绑定接收服务、操作者、仓库、分支、基线、所选树与说明。首次写入和重试均先以分支、基线和候选 OID 查询接收状态。若该提交已经进入分支父链，直接取回原回执。服务已接收且响应遗失时，重新点击可取回原提交；其他操作先推进分支时，界面要求重新同步和选择。G12、G13 可消费回执中的分支和完整 OID。

## 接入、验证与回退

原生控件通过 `editor/SCsub` 编入编辑器。配套宿主由工作流 Python 执行 `tianshu_bridge.py` 和 `selected_commit.py`，使用 G10 已有的服务地址与账户会话。服务新增 `POST /api/v1/git/repos/{name}/selected-commits` 接收和 `GET /api/v1/git/repos/{name}/selected-commits/{sha}` 回读。项目目录、Git 工作副本、目标裸库是实际输入。回退可恢复先前的编辑器、宿主脚本和服务端；已接收提交、工作区文件、原始暂存内容和本地候选引用可继续用 Git 读取。

运行 `tests/editor/run_workbench_duobao_commit.py --godot <候选编辑器> --report <回执>`，探针以独立编辑器、真实账户和回环 API 选择 A 并双击，令服务在成功更新后丢失首次回执，再点击重试。探针独立读取多宝分支、提交计数、本地 HEAD 以及 B 的索引与磁盘内容。[定向验证回执](../data-collection/gonggong-ai-workbench-plan1-g11.json) · [原生探针](../tests/editor/workbench_duobao_commit.gd) · [Git 与接口回归](../customizations/components/tianxuan/server/test_selected_commit.py)

macOS 第七轮在 `17938f86` 使用原生物化项目和认证批次，由调用方选 A，并在服务重启后核对相同修订与原请求键。Windows 的 `tests/editor/run_workbench_duobao_native_commit.py --godot <候选编辑器> --report <回执>` 在无 Git 的真实物化工程中打开原生控件，勾选 A、保留 B 并双击提交。成功落库后测试服务丢弃回执，结束服务进程和编辑器，按原端口与数据库重启两者。用户再次勾选 A 时查回原批次，随后独立下载精确修订的 A、B 并比较磁盘字节。本次请求匹配一条批次回执，模块一共两个修订（含种子）。[macOS 观察](https://github.com/zhzyx/nightmarish-spooky-sorceryze/issues/1838#issuecomment-7065757542) · [Windows 原生批次探针](../tests/editor/run_workbench_duobao_native_commit.py)
