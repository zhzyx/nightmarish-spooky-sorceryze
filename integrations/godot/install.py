"""Install the additive adapter without replacing existing Godot customizations."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil


def prepare(engine, destination):
    source = Path(__file__).parent
    target = engine / "editor/docks/ai_chat_dock.cpp"
    original = target.read_bytes()
    text = original.decode("utf-8")
    marker = '#include "olympus_panel.h"'
    if marker in text:
        raise ValueError("Adapter already installed; inspect existing version before updating")
    anchor = '\tworkspace_pages->set_tab_title(1, U"定时器");'
    if text.count(anchor) != 1:
        raise ValueError("AI workspace hook changed; manual merge required")
    newline = "\r\n" if b"\r\n" in original else "\n"
    text = text.replace('#include "ai_chat_dock.h"', '#include "ai_chat_dock.h"' + newline + marker, 1)
    text = text.replace(anchor, anchor + newline + '\tworkspace_pages->add_child(memnew(OlympusPanel));' + newline + '\tworkspace_pages->set_tab_title(2, "Olympus");', 1)
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "ai_chat_dock.cpp.before").write_bytes(original)
    (destination / "ai_chat_dock.cpp.after").write_bytes(text.encode("utf-8"))
    patch = ''.join(difflib.unified_diff(original.decode().splitlines(True), text.splitlines(True),
                                       fromfile="a/editor/docks/ai_chat_dock.cpp", tofile="b/editor/docks/ai_chat_dock.cpp"))
    (destination / "engine.patch").write_text(patch, encoding="utf-8", newline="")
    return target, original, text.encode("utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--engine", type=Path, required=True)
    p.add_argument("--backup", type=Path, required=True)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    target, before, after = prepare(a.engine, a.backup)
    pairs = [(Path(__file__).parent / name, a.engine / folder / name) for name, folder in
             [("olympus_panel.h", "editor/docks"), ("olympus_panel.cpp", "editor/docks"), ("olympus_bridge.py", "tools")]]
    if any(dst.exists() for _, dst in pairs):
        raise ValueError("Existing adapter file; refusing overwrite")
    report = {"historical_base": "unavailable_no_engine_git_metadata", "framework_modified": False,
              "engine_hook_before_sha256": hashlib.sha256(before).hexdigest(),
              "engine_hook_after_sha256": hashlib.sha256(after).hexdigest(),
              "applied": a.apply, "new_files": [dst.relative_to(a.engine).as_posix() for _, dst in pairs]}
    if a.apply:
        if target.read_bytes() != before:
            raise ValueError("Source changed during merge")
        for src, dst in pairs:
            shutil.copyfile(src, dst)
        target.write_bytes(after)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
