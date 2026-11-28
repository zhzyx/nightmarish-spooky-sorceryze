"""Copy a GDExtension Terrain3D project for use with the native-module editor."""

import argparse
import re
import shutil
import tempfile
from pathlib import Path

LEGACY = Path("addons/terrain_3d")
NEW_ASSETS = Path("terrain3d_legacy")
PLUGIN_PATH = "res://addons/terrain_3d/"
PLUGIN_REGISTRATION = PLUGIN_PATH + "plugin.cfg"
TEXT_FORMATS = {
    ".cfg",
    ".cs",
    ".csproj",
    ".gd",
    ".gdextension",
    ".gdshader",
    ".gdshaderinc",
    ".godot",
    ".import",
    ".ini",
    ".json",
    ".svg",
    ".tres",
    ".tscn",
    ".xml",
}


def remove_registration(text):
    # Only remove Terrain3D's entry. Other enabled plugins keep their order.
    def update_setting(match):
        value = match[0]
        entry = re.escape('"' + PLUGIN_REGISTRATION + '"')
        value = re.sub(entry + r"\s*,\s*", "", value)
        value = re.sub(r"\s*,\s*" + entry, "", value)
        return re.sub(entry, "", value)

    return re.sub(r"(?ms)^\[editor_plugins\][^\[]*?^enabled\s*=\s*PackedStringArray\([^)]*\)", update_setting, text)


def copy_project(source, destination, keep_paths):
    if not (source / "project.godot").is_file():
        raise ValueError(f"Not a Godot project: {source}")
    if not (source / LEGACY / "terrain.gdextension").is_file():
        raise ValueError(f"Legacy terrain.gdextension is missing under {source / LEGACY}")
    if destination.exists() or source in destination.parents:
        raise ValueError("Choose a new destination outside the source project")
    if not keep_paths and (source / NEW_ASSETS).exists():
        raise ValueError(f"Existing project directory conflicts with migration target: {NEW_ASSETS}")

    target_assets = LEGACY if keep_paths else NEW_ASSETS
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".terrain3d-migrate-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "project"

        def ignore(directory, names):
            relative = Path(directory).relative_to(source)
            if relative == Path("."):
                return set(names) & {".git", ".godot", ".mono"}
            if relative == LEGACY.parent:
                return {LEGACY.name}
            return set()

        shutil.copytree(source, stage, ignore=ignore)

        def runtime_only(directory, names):
            if Path(directory) == source / LEGACY:
                omitted = {"bin", "plugin.cfg", "terrain.gdextension", "terrain.gdextension.uid"}
                if not keep_paths:
                    omitted.update({"src", "menu"})
                return set(names) & omitted
            return set()

        (stage / target_assets).parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source / LEGACY, stage / target_assets, ignore=runtime_only)
        pending = list(stage.rglob("*"))
        while pending:
            path = pending.pop()
            if not path.is_file() or path.suffix.lower() not in TEXT_FORMATS:
                continue
            original = path.read_bytes()
            try:
                text = original.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if path == stage / "project.godot":
                text = remove_registration(text)
            if not keep_paths:
                # Preserve explicitly used custom scripts and their relative sibling dependencies.
                for name in ("src", "menu"):
                    extra = stage / target_assets / name
                    if PLUGIN_PATH + name + "/" in text and not extra.exists() and (source / LEGACY / name).is_dir():
                        shutil.copytree(source / LEGACY / name, extra)
                        pending.extend(extra.rglob("*"))
                text = text.replace(PLUGIN_PATH, f"res://{target_assets.as_posix()}/")
            data = text.encode("utf-8")
            if data != original:
                path.write_bytes(data)
        if (stage / "addons").exists() and not any((stage / "addons").iterdir()):
            (stage / "addons").rmdir()
        stage.rename(destination)
    print(f"Native project: {destination}")
    print(f"Legacy runtime scripts and project assets: res://{target_assets.as_posix()}/")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path, help="A new directory; the source project is preserved")
    parser.add_argument(
        "--keep-resource-paths",
        action="store_true",
        help="Keep resource paths for binary scenes and runtime-generated path references",
    )
    args = parser.parse_args()
    try:
        copy_project(args.source.resolve(), args.destination.resolve(), args.keep_resource_paths)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
