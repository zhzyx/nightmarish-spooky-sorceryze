import json
from pathlib import Path


def framework_root(root):
    root = Path(root).resolve()
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
