# H05 按提交版本签认创意候选

在工单的「并排比较候选」窗口，每栏的「查看或判断此版本」打开该栏所选的提交。判断面板显示工单号、提交版本、文件路径、完整修订和当前判断人。当前判断人可以填写意见并采纳或退回；其他成员可以查看该版本的判断状态与签认记录。

提交沿用天璇的版本化判断接口。服务核对判断人、工单版本和所选原件，并将签认人、提交号、修订、文件摘要、结论和意见写入工单历史。其他候选保留原状态。旧客户端以原件引用提交判断时，若多个待判断项指向同一原件，服务要求提供明确的提交号。原请求重放返回第一次的回执，更换目标须使用新的请求标识并重新核对判断权限。

在仓库根用 Windows 候选编辑器运行以下验证。静默编辑器场景覆盖两位测试账号、两栏原件、责任转交、陈旧页面、重复请求、退回意见、AI 工具入口和重开数据库后的记录；具体创意取舍由该版本的判断人作出。

```powershell
python -X utf8 tests/editor/run_workbench_creative_judgments.py --godot bin/godot.windows.editor.x86_64.console.exe --report "$env:TEMP/h05-result.json"
```

服务回归覆盖签认、已批准原件读取、Godot 导入、附件和工单生命周期。以下 Python 片段可从仓库根以同一测试环境运行，编辑器与导入项目使用系统临时目录。

```python
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "tests/editor")
from editor_test_isolation import copy_editor
from run_unified_settings_native import sanitized_environment

os.environ["GONGGONG_WORKSPACE"] = ""
with tempfile.TemporaryDirectory(prefix="h05-regress-") as fixture:
    base = Path(fixture)
    engine = copy_editor(Path("bin/godot.windows.editor.x86_64.exe"), base / "engine")
    env = sanitized_environment(base) | {"TIANXUAN_GODOT_EXECUTABLE": str(engine), "PYTHONUTF8": "1"}
    server = Path("customizations/components/tianxuan/server")
    suites = ["work_management", "approved_asset", "godot_inputs", "issue_artifacts", "issue_lifecycle"]
    subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--basetemp", str(base / "data"),
         *[str(server / f"test_{suite}.py") for suite in suites]],
        env=env, check=True,
    )
```

[设计条款](gonggong-ai-workbench-plan1.md#h05) · [Windows 定向验证回执](../data-collection/gonggong-ai-workbench-plan1-h05.json)
