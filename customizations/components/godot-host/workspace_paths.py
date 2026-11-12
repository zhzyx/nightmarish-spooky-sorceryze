import json
from pathlib import Path


def framework_root(root):
    # Framework admission belongs to this installed adapter, not candidate files.
    root = Path(__file__).resolve().parents[3]
    pointer = json.loads((root / "CURRENT_FRAMEWORK.json").read_text(encoding="utf-8"))
    if pointer.get("path_base") != "this_file_directory":
        raise ValueError("Unsupported framework pointer base")
    relative = Path(pointer["root"])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Framework pointer must remain in workspace")
    target = (root / relative).resolve()
    target.relative_to(root)
    if not (target / pointer["manifest"]).is_file():
        raise ValueError("Framework manifest missing")
    return target


def prepare_game_workspace(root, work):
    """Initialize data only for the current authenticated GitHub game repository.

    Paths are relative to the selected Git root. No installed executable, framework
    or credential is copied. Existing user data is preserved and identity is read
    again by the ordinary Issue gate for every execution.
    """
    import os
    import re
    import subprocess
    import uuid
    from datetime import datetime, timezone

    root = Path(root).absolute()
    if root.resolve() != root:
        raise ValueError("游戏工作区包含链接，请从真实项目路径重新打开。")
    if (root / "work-items.json").is_file():
        return

    def git(*args):
        result = subprocess.run(
            [os.environ.get("GONGGONG_GIT", "git"), "-C", str(root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        if result.returncode:
            raise ValueError("游戏项目需要已提交的 Git 仓库和真实 GitHub origin；请先初始化并配置来源后重试。")
        return result.stdout.strip()

    if Path(git("rev-parse", "--show-toplevel")).resolve() != root:
        raise ValueError("请选择游戏项目所属 Git 仓库根目录。")
    git("rev-parse", "--verify", "HEAD")
    origin = git("remote", "get-url", "origin")
    match = re.fullmatch(
        r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?",
        origin,
    )
    if not match:
        raise ValueError("游戏仓库 origin 必须指向真实 GitHub 仓库；请配置来源后重试。")
    repository = match[1]
    # Never borrow the installation repository's identity or permissions.
    user = json.loads(work.gh("api", "user"))
    remote = json.loads(work.gh("api", "repos/" + repository))
    if (
        not user.get("login")
        or type(user.get("id")) is not int
        or remote.get("full_name", "").casefold() != repository.casefold()
        or remote.get("permissions", {}).get("push") is not True
    ):
        raise ValueError("当前 GitHub 账号需要游戏仓库的写权限；请连接有权账号后重试。")
    installation = Path(__file__).resolve().parents[3]
    settings = {
        "schema_version": 1,
        "provider": "github_issues",
        "repository": repository,
        "tenant_id": "gonggong-workspace",
        "requirements_root": "design-docs",
        "collection_root": "data-collection",
        "canonical_events_root": "gonggong-diting-data",
        "category_labels": ".github/labels.json",
        "status_labels": ".github/status-labels.json",
        "host_binding": "installed_game_workspace_v1",
        "path_base": "repository_root",
    }
    planned = {"work-items.json": settings}
    for name in (".github/labels.json", ".github/status-labels.json"):
        planned[name] = json.loads((installation / name).read_text(encoding="utf-8"))
    planned["gonggong-diting-data/dataset.json"] = {
        "schema_version": 1,
        "dataset_id": str(uuid.uuid4()),
        "origin_framework": "gonggong",
        "name": "gonggong-diting-data",
        "storage": "immutable_event_json",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # Preflight the complete write set before creating anything; never replace user files.
    for name, value in planned.items():
        target = root / name
        if target.resolve() != target:
            raise ValueError("游戏工作区配置路径包含链接：" + name)
        if target.exists():
            existing = json.loads(target.read_text(encoding="utf-8"))
            if name.endswith("dataset.json"):
                if existing.get("origin_framework") != "gonggong" or existing.get("storage") != "immutable_event_json":
                    raise ValueError("已有数据集不兼容，请保留并核对配置。")
            elif existing != value:
                raise ValueError("已有游戏工作区配置不同，请保留并核对：" + name)
    # Config is the completion marker, written last so interrupted setup can resume.
    for name in [n for n in planned if n != "work-items.json"] + ["work-items.json"]:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open("x", encoding="utf-8") as stream:
                json.dump(planned[name], stream, ensure_ascii=False, indent=2)
                stream.write("\n")
        except FileExistsError:
            pass
