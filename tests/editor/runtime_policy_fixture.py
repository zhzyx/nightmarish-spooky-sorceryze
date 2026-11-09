"""Copy the exact trusted host policy inputs into private test installations."""

import shutil

POLICY_FILES = (
    "CURRENT_FRAMEWORK.json",
    "framework/framework-manifest.json",
    "framework/foundation.lock.json",
    "framework/FOUNDATION.md",
    "framework/AGENTS.md",
    "framework/GOVERNANCE.md",
    "framework/specs/model-runtime.md",
    "framework/upstream/yuanheng/core.md",
    "framework/upstream/yuanheng/agents/yuanheng.md",
    "customizations/components/godot-host/README.md",
)


def copy_runtime_policy(source, destination):
    for relative in (*POLICY_FILES, "tools/gonggong_runtime_policy.ps1"):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
